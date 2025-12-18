"""Step-by-step onboarding flow with X account connection"""
from typing import Dict, Any, Optional, List
from core.persona_state import load_persona_state, save_persona_state
from core.auth import update_user, get_user_data_dir, load_users, save_users
from services.x_api import get_user_timeline, get_user_likes, get_user_replies, get_current_user
from services.ai_service import client
from features.account_discovery import discover_accounts_for_user, get_posts_for_onboarding
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
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not connect to X account: {str(e)}. Please check your API keys."
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
    
    # Save relevance preferences and move to next step
    users[user_id]["keyword_relevance"] = keyword_relevance
    users[user_id]["onboarding_step"] = 4
    save_users(users)
    
    return {
        "success": True,
        "message": "Relevance preferences saved",
        "step": 4
    }


def get_onboarding_suggestions(user_id: str) -> Dict[str, Any]:
    """
    Step 4: Get suggestions for following onboarding
    
    Args:
        user_id: User ID
    
    Returns:
        Dict with suggested accounts, posts, likes, replies
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    user = users[user_id]
    keywords = user.get("keywords", [])
    keyword_relevance = user.get("keyword_relevance", {})
    
    if not keywords or not keyword_relevance:
        return {
            "success": False,
            "error": "Keywords and relevance preferences required"
        }
    
    # Get suggestions
    accounts = discover_accounts_for_user(keywords, keyword_relevance, user_id)
    posts_to_like = get_posts_for_onboarding(keywords, keyword_relevance, 'like', 20)
    posts_to_reply = get_posts_for_onboarding(keywords, keyword_relevance, 'reply', 15)
    posts_to_engage = get_posts_for_onboarding(keywords, keyword_relevance, 'engage', 15)
    
    return {
        "success": True,
        "accounts": accounts[:20],  # Top 20 accounts
        "posts_to_like": posts_to_like,
        "posts_to_reply": posts_to_reply,
        "posts_to_engage": posts_to_engage
    }


def save_onboarding_choices(
    user_id: str,
    followed_accounts: List[str],
    liked_posts: List[str],
    replied_posts: List[str],
    engaged_posts: List[str]
) -> Dict[str, Any]:
    """
    Step 4: Save user's onboarding choices and complete onboarding
    
    Args:
        user_id: User ID
        followed_accounts: List of account IDs user chose to follow
        liked_posts: List of post IDs user liked
        replied_posts: List of post IDs user replied to
        engaged_posts: List of post IDs user engaged with
    
    Returns:
        Result dict
    """
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    # Save choices
    users[user_id]["onboarding_choices"] = {
        "followed_accounts": followed_accounts,
        "liked_posts": liked_posts,
        "replied_posts": replied_posts,
        "engaged_posts": engaged_posts
    }
    
    # Update persona state based on choices
    _update_persona_from_choices(user_id, followed_accounts, liked_posts, replied_posts, engaged_posts)
    
    # Complete onboarding
    users[user_id]["onboarding_complete"] = True
    users[user_id]["onboarding_step"] = 5
    save_users(users)
    
    return {
        "success": True,
        "message": "Onboarding complete!",
        "step": "complete"
    }


def _update_persona_from_choices(
    user_id: str,
    followed_accounts: List[str],
    liked_posts: List[str],
    replied_posts: List[str],
    engaged_posts: List[str]
) -> None:
    """Update persona state based on onboarding choices"""
    from core.persona_state import load_persona_state, save_persona_state
    from core.learning_loop import process_behavioral_feedback
    
    state = load_persona_state(user_id)
    users = load_users()
    user = users.get(user_id)
    keywords = user.get("keywords", [])
    keyword_relevance = user.get("keyword_relevance", {})
    
    # Update topic affinity based on keywords and relevance
    for keyword, relevance in keyword_relevance.items():
        # Map keyword to topic categories
        topic = _keyword_to_topic(keyword)
        if topic:
            state["topic_affinity"][topic] = relevance
    
    # Process behavioral feedback
    for _ in liked_posts:
        process_behavioral_feedback("like", {"keywords": keywords}, user_id)
    
    for _ in replied_posts:
        process_behavioral_feedback("reply", {"keywords": keywords}, user_id)
    
    for _ in followed_accounts:
        process_behavioral_feedback("follow", {"keywords": keywords}, user_id)
    
    # Update engagement behavior
    state["engagement_behavior"]["replies_per_day_baseline"] = max(1, len(replied_posts) // 7)
    state["engagement_behavior"]["likes_per_day_baseline"] = max(5, len(liked_posts) // 7)
    
    save_persona_state(state, user_id)


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



