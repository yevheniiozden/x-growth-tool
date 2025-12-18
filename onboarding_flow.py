"""Step-by-step onboarding flow with X account connection"""
from typing import Dict, Any, Optional, List
from core.persona_state import load_persona_state, save_persona_state
from core.auth import update_user, get_user_data_dir, load_users, save_users
from services.x_api import get_user_timeline, get_user_likes, get_user_replies, get_current_user
from services.ai_service import client
from features.account_discovery import discover_accounts_for_user, get_posts_for_onboarding
from datetime import datetime
import json


def get_onboarding_step(user_id: str) -> Dict[str, Any]:
    """Get current onboarding step for user"""
    users = load_users()
    user = users.get(user_id)
    
    if not user:
        return {"step": 1, "message": "User not found"}
    
    step = user.get("onboarding_step", 1)
    x_connected = user.get("x_connected", False)
    onboarding_complete = user.get("onboarding_complete", False)
    
    if onboarding_complete:
        return {
            "step": "complete",
            "message": "Onboarding complete",
            "x_connected": x_connected
        }
    
    return {
        "step": step,
        "x_connected": x_connected,
        "x_username": user.get("x_username"),
        "keywords": user.get("keywords", []),
        "keyword_relevance": user.get("keyword_relevance", {}),
        "message": _get_step_message(step, x_connected)
    }


def _get_step_message(step: int, x_connected: bool) -> str:
    """Get message for current step"""
    messages = {
        1: "Welcome! Let's connect your X account to get started.",
        2: "Great! Now let's identify your interests and topics.",
        3: "Perfect! Let's fine-tune your preferences.",
        4: "Now let's discover accounts and content you'll love.",
        5: "Onboarding complete! Your AI brain is ready."
    }
    return messages.get(step, "Continue setup")


def connect_x_account(user_id: str, x_username: str) -> Dict[str, Any]:
    """
    Step 1: Connect X account
    
    Args:
        user_id: User ID
        x_username: X username (without @)
    
    Returns:
        Result dict
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    # Test connection by trying to fetch user data
    try:
        import requests
        timeline = get_user_timeline(x_username, days_back=1, max_results=1)
        # If we can fetch, connection works
        users[user_id]["x_username"] = x_username
        users[user_id]["x_connected"] = True
        users[user_id]["onboarding_step"] = 2
        save_users(users)
        
        return {
            "success": True,
            "message": "X account connected successfully",
            "step": 2
        }
    except requests.exceptions.ReadTimeout:
        return {
            "success": False,
            "error": "Connection timed out. The X API is slow right now. Please try again."
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Network error: {str(e)}. Please check your connection and try again."
        }
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return {
                "success": False,
                "error": "Connection timed out. Please try again."
            }
        return {
            "success": False,
            "error": f"Could not connect to X account: {error_msg}. Please check your API keys."
        }


def save_keywords(user_id: str, keywords: List[str]) -> Dict[str, Any]:
    """
    Step 2: Save user keywords
    
    Args:
        user_id: User ID
        keywords: List of keywords (minimum 3)
    
    Returns:
        Result dict
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    # Validate keywords
    keywords = [k.strip() for k in keywords if k.strip()]
    if len(keywords) < 3:
        return {
            "success": False,
            "error": "Please provide at least 3 keywords for better results"
        }
    
    # Save keywords and move to next step
    users[user_id]["keywords"] = keywords
    users[user_id]["onboarding_step"] = 3
    save_users(users)
    
    return {
        "success": True,
        "message": "Keywords saved successfully",
        "keywords": keywords,
        "step": 3
    }


def save_keyword_relevance(user_id: str, keyword_relevance: Dict[str, float]) -> Dict[str, Any]:
    """
    Step 3: Save keyword relevance preferences
    
    Args:
        user_id: User ID
        keyword_relevance: Dict mapping keywords to relevance scores (0.1-1.0)
    
    Returns:
        Result dict
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    # Validate relevance scores
    for keyword, score in keyword_relevance.items():
        if not 0.1 <= score <= 1.0:
            return {
                "success": False,
                "error": f"Relevance score for '{keyword}' must be between 10% and 100%"
            }
    
    # Save relevance preferences and initialize interactive onboarding
    users[user_id]["keyword_relevance"] = keyword_relevance
    users[user_id]["onboarding_step"] = 4
    users[user_id]["interactive_onboarding"] = {
        "phase": 1,
        "phase1_index": 0,
        "phase2_index": 0,
        "phase3_index": 0,
        "phase4_index": 0,
        "phase1_responses": [],
        "phase2_responses": [],
        "phase3_responses": [],
        "phase4_responses": [],
        "data_preparing": True  # Flag to indicate data is being prepared
    }
    save_users(users)
    
    # Note: _prepare_onboarding_data will be called as background task in the endpoint
    # Return immediately - data preparation happens asynchronously
    
    return {
        "success": True,
        "message": "Relevance preferences saved",
        "step": 4,
        "data_preparing": True
    }


def get_interactive_onboarding_status(user_id: str) -> Dict[str, Any]:
    """
    Get current interactive onboarding status
    
    Args:
        user_id: User ID
    
    Returns:
        Dict with phase, progress, and status
    """
    users = load_users()
    if user_id not in users:
        return {"active": False, "error": "User not found"}
    
    user = users[user_id]
    interactive = user.get("interactive_onboarding", {})
    
    if not interactive:
        return {"active": False}
    
    phase = interactive.get("phase", 1)
    
    # Calculate progress for current phase
    phase_index_key = f"phase{phase}_index"
    current_index = interactive.get(phase_index_key, 0)
    
    # Get response counts for detailed progress
    phase_responses_key = f"phase{phase}_responses"
    responses = interactive.get(phase_responses_key, [])
    
    # Count responses by type - handle both old and new response formats
    liked_count = 0
    skipped_count = 0
    engaged_count = 0
    
    for r in responses:
        if not r:
            continue
        response_val = r.get('response') or r.get('response_value') or r.get('response_type', '')
        response_value = r.get('response_value') or r.get('response', '')
        
        # Phase 1, 3, 4: yes/like/subscribe = liked, no/skip = skipped
        if phase in [1, 3, 4]:
            if response_val in ['yes', 'like', 'subscribe'] or response_value in ['yes', 'like', 'subscribe']:
                liked_count += 1
            elif response_val in ['no', 'skip'] or response_value in ['no', 'skip']:
                skipped_count += 1
        # Phase 2: yes = engaged, no = skipped
        elif phase == 2:
            if response_val == 'yes' or response_value == 'yes':
                engaged_count += 1
            elif response_val == 'no' or response_value == 'no':
                skipped_count += 1
    
    # Get total items for this phase
    total_items = {
        1: 20,  # Content preference
        2: 10,  # Engagement preference
        3: 20,  # Like/skip preference
        4: 10   # Profile subscription
    }.get(phase, 20)
    
    # Calculate overall progress across all phases
    total_phases = 4
    completed_phases = phase - 1
    phase_progress = (current_index + 1) / total_items if total_items > 0 else 0
    overall_progress = (completed_phases + phase_progress) / total_phases
    
    remaining = max(0, total_items - (current_index + 1))
    
    return {
        "active": True,
        "phase": phase,
        "current_index": current_index,
        "total": total_items,
        "progress": min(1.0, overall_progress),
        "phase_progress": phase_progress,
        "remaining": remaining,
        "liked": liked_count,
        "skipped": skipped_count,
        "engaged": engaged_count,
        "completed": current_index + 1
    }


def get_next_onboarding_post(user_id: str, phase: int) -> Dict[str, Any]:
    """
    Get next post for interactive onboarding phase
    
    Args:
        user_id: User ID
        phase: Phase number (1, 2, or 3)
    
    Returns:
        Post data or error
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    user = users[user_id]
    interactive = user.get("interactive_onboarding", {})
    keywords = user.get("keywords", [])
    keyword_relevance = user.get("keyword_relevance", {})
    
    # Get cached posts or fetch new ones
    cache_key = f"onboarding_posts_phase{phase}"
    user_dir = get_user_data_dir(user_id)
    cache_file = user_dir / f"{cache_key}.json"
    
    posts = []
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                posts = json.load(f)
            print(f"Loaded {len(posts)} cached posts for phase {phase} from {cache_file}")
        except Exception as e:
            print(f"Error loading cached posts from {cache_file}: {e}")
            pass
    
    # If no cached posts, check if background task is still preparing data
    if not posts:
        data_preparing = interactive.get("data_preparing", False)
        if data_preparing:
            # Background task is still running - return placeholder and let user wait
            print(f"No cached posts found for phase {phase}, background task is preparing data...")
            return {
                "success": True,
                "post": {
                    "id": f"loading_{phase}",
                    "text": "Loading posts... Please wait a moment while we fetch relevant content for you.",
                    "author_username": "system",
                    "likes": 0,
                    "replies": 0,
                    "relevance_score": 0.5,
                    "url": None
                },
                "index": 0,
                "total": 1,
                "loading": True
            }
        
        # No cache found - try quick fetch for immediate results, then trigger AI in background
        print(f"No cached posts found for phase {phase}, attempting quick fetch...")
        try:
            # Use fast mode for immediate results (non-blocking)
            from features.account_discovery import get_posts_for_onboarding
            from datetime import datetime
            
            if phase == 1:
                posts = get_posts_for_onboarding(keywords, keyword_relevance, 'like', 20, fast_mode=True)
            elif phase == 2:
                posts = get_posts_for_onboarding(keywords, keyword_relevance, 'reply', 10, fast_mode=True)
            elif phase == 3:
                posts = get_posts_for_onboarding(keywords, keyword_relevance, 'engage', 20, fast_mode=True)
            
            print(f"Quick fetch returned {len(posts)} posts for phase {phase}")
            
            # Cache posts with metadata (fast mode, not AI-enhanced)
            cache_data = {
                "ai_enhanced": False,
                "timestamp": datetime.now().isoformat(),
                "preparing": False,
                "posts": posts if posts else []
            }
            
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
                print(f"Cached {len(posts)} posts (fast mode) to {cache_file}")
            except Exception as e:
                print(f"Error caching posts to {cache_file}: {e}")
            
            # Trigger AI enhancement in background (non-blocking)
            # This will update cache with AI-enhanced results when ready
            try:
                from threading import Thread
                def enhance_with_ai():
                    try:
                        print(f"Starting AI enhancement for phase {phase} in background...")
                        # Mark cache as preparing
                        cache_data["preparing"] = True
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, indent=2, ensure_ascii=False)
                        
                        # Get AI-enhanced posts
                        if phase == 1:
                            ai_posts = get_posts_for_onboarding(keywords, keyword_relevance, 'like', 20, fast_mode=False)
                        elif phase == 2:
                            ai_posts = get_posts_for_onboarding(keywords, keyword_relevance, 'reply', 10, fast_mode=False)
                        elif phase == 3:
                            ai_posts = get_posts_for_onboarding(keywords, keyword_relevance, 'engage', 20, fast_mode=False)
                        
                        # Update cache with AI-enhanced results
                        cache_data["ai_enhanced"] = True
                        cache_data["preparing"] = False
                        cache_data["timestamp"] = datetime.now().isoformat()
                        cache_data["posts"] = ai_posts if ai_posts else posts  # Fallback to fast mode posts if AI fails
                        
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, indent=2, ensure_ascii=False)
                        print(f"AI enhancement completed for phase {phase}: {len(ai_posts)} posts")
                    except Exception as e:
                        print(f"Error in AI enhancement for phase {phase}: {e}")
                        # Mark as not preparing if enhancement fails
                        cache_data["preparing"] = False
                        try:
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                        except:
                            pass
                
                # Start AI enhancement in background thread
                Thread(target=enhance_with_ai, daemon=True).start()
            except Exception as e:
                print(f"Error starting AI enhancement thread: {e}")
                
        except Exception as e:
            print(f"Error fetching posts for phase {phase}: {e}")
            import traceback
            traceback.print_exc()
            posts = []  # Empty list - will return placeholder below
    
    # Filter out posts without URLs (they can't be embedded)
    posts_with_urls = [p for p in posts if p.get('url')]
    if len(posts_with_urls) < len(posts):
        print(f"Filtered out {len(posts) - len(posts_with_urls)} posts without URLs (phase {phase})")
    posts = posts_with_urls
    
    # Store AI-enhanced flag for response
    ai_enhanced_flag = ai_enhanced
    
    current_index = interactive.get(f"phase{phase}_index", 0)
    print(f"Current index for phase {phase}: {current_index}, Total posts: {len(posts)}")
    
    if not posts or current_index >= len(posts):
        # If no posts available (API error), return a placeholder post
        if not posts:
            print(f"No posts available for phase {phase}, returning placeholder")
            return {
                "success": True,
                "post": {
                    "id": f"placeholder_{phase}_{current_index}",
                    "text": "No posts available at this time. Please check your X API configuration. You can still proceed with onboarding.",
                    "author_username": "system",
                    "likes": 0,
                    "replies": 0,
                    "relevance_score": 0.5,
                    "url": None  # No URL for placeholder - frontend will handle this
                },
                "index": current_index,
                "total": 1,
                "placeholder": True,
                "ai_enhanced": ai_enhanced_flag
            }
        print(f"Index {current_index} >= total posts {len(posts)} for phase {phase}")
        return {"success": False, "error": "No more posts in this phase"}
    
    # Get the post and ensure it has a URL
    post = posts[current_index]
    
    # If post doesn't have a URL, try to construct it from available data
    if not post.get('url'):
        author_username = post.get('author_username') or post.get('username')
        post_id = post.get('id')
        if author_username and post_id:
            post['url'] = f"https://twitter.com/{author_username}/status/{post_id}"
        else:
            # If we can't construct URL, log warning but still return post
            print(f"Warning: Post {post.get('id')} missing URL and cannot construct it")
            post['url'] = None
    
    return {
        "success": True,
        "post": post,
        "index": current_index,
        "total": len(posts),
        "ai_enhanced": ai_enhanced_flag  # Indicate if these are AI-enhanced results
    }


def get_next_onboarding_profile(user_id: str) -> Dict[str, Any]:
    """
    Get next profile for phase 4
    
    Args:
        user_id: User ID
    
    Returns:
        Profile data with feed or error
    """
    from features.account_discovery import get_account_feed, get_account_details
    
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    user = users[user_id]
    interactive = user.get("interactive_onboarding", {})
    keywords = user.get("keywords", [])
    keyword_relevance = user.get("keyword_relevance", {})
    
    # Get cached accounts or fetch new ones
    user_dir = get_user_data_dir(user_id)
    cache_file = user_dir / "onboarding_accounts.json"
    
    accounts = []
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
        except:
            pass
    
    # If no cached accounts, fetch them
    if not accounts:
        accounts = discover_accounts_for_user(keywords, keyword_relevance, user_id)
        # Cache accounts
        if accounts:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, indent=2, ensure_ascii=False)
    
    current_index = interactive.get("phase4_index", 0)
    
    if not accounts or current_index >= len(accounts):
        # If no accounts available (API error), return a placeholder account
        if not accounts:
            return {
                "success": True,
                "account": {
                    "id": f"placeholder_account_{current_index}",
                    "username": "example_account",
                    "name": "Example Account",
                    "description": "No accounts available at this time. Please check your X API configuration. You can still proceed with onboarding.",
                    "followers": 0,
                    "tweets": 0,
                    "verified": False
                },
                "feed": [],
                "index": current_index,
                "total": 1,
                "placeholder": True
            }
        return {"success": False, "error": "No more profiles in this phase"}
    
    account = accounts[current_index]
    
    # Get full account details and feed (handle errors gracefully)
    try:
        account_details = get_account_details(account.get("id"))
        if account_details:
            account.update(account_details)
    except Exception as e:
        print(f"Error getting account details: {e}")
        # Continue with basic account info
    
    try:
        feed = get_account_feed(account.get("id"), max_posts=20)
    except Exception as e:
        print(f"Error getting account feed: {e}")
        feed = []
    
    return {
        "success": True,
        "account": account,
        "feed": feed or [],
        "index": current_index,
        "total": len(accounts)
    }


def save_onboarding_response(
    user_id: str,
    phase: int,
    post_id: Optional[str],
    account_id: Optional[str],
    response_type: str,
    response_value: Any
) -> Dict[str, Any]:
    """
    Save user response and update persona state
    
    Args:
        user_id: User ID
        phase: Phase number (1-4)
        post_id: Post ID (for phases 1-3)
        account_id: Account ID (for phase 4)
        response_type: Type of response ('like', 'skip', 'yes', 'no', 'subscribe')
        response_value: Response value (True/False or string)
    
    Returns:
        Result dict
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    user = users[user_id]
    interactive = user.get("interactive_onboarding", {})
    
    # Save response
    response = {
        "post_id": post_id,
        "account_id": account_id,
        "response_type": response_type,
        "response_value": response_value,
        "timestamp": datetime.now().isoformat()
    }
    
    responses_key = f"phase{phase}_responses"
    if responses_key not in interactive:
        interactive[responses_key] = []
    interactive[responses_key].append(response)
    
    # Update index
    index_key = f"phase{phase}_index"
    interactive[index_key] = interactive.get(index_key, 0) + 1
    
    users[user_id]["interactive_onboarding"] = interactive
    save_users(users)
    
    # Get post/account data for persona update
    if post_id:
        # Fetch post data if needed
        user_dir = get_user_data_dir(user_id)
        for phase_num in [1, 2, 3]:
            cache_file = user_dir / f"onboarding_posts_phase{phase_num}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        posts = json.load(f)
                        for post in posts:
                            if post.get("id") == post_id:
                                response["post_text"] = post.get("text", "")
                                break
                except:
                    pass
    
    if account_id:
        # Fetch account data if needed
        user_dir = get_user_data_dir(user_id)
        cache_file = user_dir / "onboarding_accounts.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    accounts = json.load(f)
                    for account in accounts:
                        if account.get("id") == account_id:
                            response["account_description"] = account.get("description", "")
                            break
            except:
                pass
    
    # Update persona state
    from core.learning_loop import process_onboarding_response
    process_onboarding_response(phase, response, user_id)
    
    # Check if phase is complete
    phase_counts = {1: 20, 2: 10, 3: 20, 4: 10}
    if interactive[index_key] >= phase_counts.get(phase, 10):
        # Move to next phase
        if phase < 4:
            interactive["phase"] = phase + 1
            users[user_id]["interactive_onboarding"] = interactive
            save_users(users)
        else:
            # All phases complete
            complete_interactive_onboarding(user_id)
    
    return {
        "success": True,
        "next_phase": interactive.get("phase", phase),
        "phase_complete": interactive[index_key] >= phase_counts.get(phase, 10)
    }


def skip_onboarding_phase(user_id: str) -> Dict[str, Any]:
    """
    Skip current onboarding phase and move to next
    
    Args:
        user_id: User ID
    
    Returns:
        Result dict
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    user = users[user_id]
    interactive = user.get("interactive_onboarding", {})
    
    if not interactive:
        return {"success": False, "error": "No active onboarding"}
    
    phase = interactive.get("phase", 1)
    
    # Move to next phase
    if phase < 4:
        interactive["phase"] = phase + 1
        # Reset index for new phase
        interactive[f"phase{phase + 1}_index"] = 0
        interactive[f"phase{phase + 1}_responses"] = []
    else:
        # Complete onboarding when skipping last phase
        from onboarding_flow import complete_interactive_onboarding
        return complete_interactive_onboarding(user_id)
    
    user["interactive_onboarding"] = interactive
    save_users(users)
    
    return {
        "success": True,
        "message": "Phase skipped",
        "next_phase": interactive.get("phase"),
        "phase_complete": False
    }


def complete_interactive_onboarding(user_id: str) -> Dict[str, Any]:
    """
    Mark interactive onboarding as complete
    
    Args:
        user_id: User ID
    
    Returns:
        Result dict
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    users[user_id]["onboarding_complete"] = True
    users[user_id]["onboarding_step"] = 5
    save_users(users)
    
    return {
        "success": True,
        "message": "Interactive onboarding complete!"
    }


def _prepare_onboarding_data(user_id: str) -> None:
    """Prepare and cache onboarding data (accounts and posts) - runs as background task"""
    try:
        users = load_users()
        user = users.get(user_id)
        if not user:
            print(f"User {user_id} not found for data preparation")
            return
        
        keywords = user.get("keywords", [])
        keyword_relevance = user.get("keyword_relevance", {})
        
        user_dir = get_user_data_dir(user_id)
        
        # Discover and cache accounts (handle API errors gracefully)
        try:
            accounts = discover_accounts_for_user(keywords, keyword_relevance, user_id)
            if accounts:
                cache_file = user_dir / "onboarding_accounts.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(accounts, f, indent=2, ensure_ascii=False)
            else:
                # If no accounts found (API error), create empty cache to allow onboarding to proceed
                cache_file = user_dir / "onboarding_accounts.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error preparing account data: {e}")
            # Create empty cache to allow onboarding to proceed
            cache_file = user_dir / "onboarding_accounts.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2, ensure_ascii=False)
        
        # Fetch and cache posts for each phase with full AI search (comprehensive, not fast_mode)
        # This runs in background, so we can use full AI without blocking
        from datetime import datetime
        
        for phase, post_type, count in [(1, 'like', 20), (2, 'reply', 10), (3, 'engage', 20)]:
            try:
                print(f"Preparing AI-enhanced posts for phase {phase} (comprehensive search)...")
                # Use full AI search (fast_mode=False) for comprehensive results
                posts = get_posts_for_onboarding(keywords, keyword_relevance, post_type, count, fast_mode=False)
                cache_file = user_dir / f"onboarding_posts_phase{phase}.json"
                
                # Cache with metadata for smart cache checking
                cache_data = {
                    "ai_enhanced": True,
                    "timestamp": datetime.now().isoformat(),
                    "preparing": False,
                    "posts": posts if posts else []
                }
                
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
                print(f"Cached {len(posts)} AI-enhanced posts for phase {phase}")
            except Exception as e:
                print(f"Error preparing posts for phase {phase}: {e}")
                import traceback
                traceback.print_exc()
                # Create empty cache with metadata to allow onboarding to proceed
                cache_file = user_dir / f"onboarding_posts_phase{phase}.json"
                cache_data = {
                    "ai_enhanced": False,
                    "timestamp": datetime.now().isoformat(),
                    "preparing": False,
                    "posts": []
                }
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        # Mark data preparation as complete
        users = load_users()
        if user_id in users:
            interactive = users[user_id].get("interactive_onboarding", {})
            interactive["data_preparing"] = False
            users[user_id]["interactive_onboarding"] = interactive
            save_users(users)
            print(f"Data preparation completed for user {user_id}")
    except Exception as e:
        print(f"Error in background data preparation: {e}")
        import traceback
        traceback.print_exc()


def get_cache_status(user_id: str, phase: int) -> Dict[str, Any]:
    """
    Get cache status for onboarding phase
    
    Args:
        user_id: User ID
        phase: Phase number (1, 2, or 3)
    
    Returns:
        Cache status dict with ready, ai_enhanced, timestamp
    """
    user_dir = get_user_data_dir(user_id)
    cache_file = user_dir / f"onboarding_posts_phase{phase}.json"
    
    if not cache_file.exists():
        return {
            "ready": False,
            "ai_enhanced": False,
            "preparing": False,
            "timestamp": None
        }
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Check if it's new format with metadata
        if isinstance(cache_data, dict) and "posts" in cache_data:
            posts = cache_data.get("posts", [])
            is_preparing = cache_data.get("preparing", False)
            timestamp_str = cache_data.get("timestamp", "")
            
            return {
                "ready": len(posts) > 0 and not is_preparing,
                "ai_enhanced": cache_data.get("ai_enhanced", False),
                "preparing": is_preparing,
                "timestamp": timestamp_str,
                "post_count": len(posts)
            }
        else:
            # Old format - assume ready but not AI-enhanced
            posts = cache_data if isinstance(cache_data, list) else []
            return {
                "ready": len(posts) > 0,
                "ai_enhanced": False,
                "preparing": False,
                "timestamp": None,
                "post_count": len(posts)
            }
    except Exception as e:
        print(f"Error reading cache status for phase {phase}: {e}")
        return {
            "ready": False,
            "ai_enhanced": False,
            "preparing": False,
            "timestamp": None
        }


def _keyword_to_topic(keyword: str) -> Optional[str]:
    """Map keyword to topic category"""
    keyword_lower = keyword.lower()
    
    topic_mapping = {
        'ai': 'ai',
        'artificial intelligence': 'ai',
        'machine learning': 'ai',
        'startup': 'startups',
        'entrepreneur': 'startups',
        'saas': 'saas',
        'software': 'saas',
        'product': 'product',
        'design': 'design',
        'marketing': 'marketing',
        'growth': 'marketing',
        'productivity': 'productivity',
        'business': 'business',
        'money': 'money',
        'tech': 'tech',
        'coding': 'tech',
        'developer': 'tech'
    }
    
    for key, topic in topic_mapping.items():
        if key in keyword_lower:
            return topic
    
    return 'general'



