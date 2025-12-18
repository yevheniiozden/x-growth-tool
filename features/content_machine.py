"""Feature 2: Content Machine + Smart Scheduler"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from core.persona_state import load_persona_state, update_from_feedback
from core.learning_loop import process_explicit_feedback
from services.ai_service import generate_posts, explain_persona_alignment
import config


def load_content_schedule(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Load content schedule from JSON"""
    if user_id:
        from core.auth import get_user_data_dir
        user_dir = get_user_data_dir(user_id)
        schedule_file = user_dir / "content_schedule.json"
    else:
        schedule_file = config.CONTENT_SCHEDULE_FILE
    
    if schedule_file.exists():
        try:
            with open(schedule_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"posts": []}
    return {"posts": []}


def save_content_schedule(schedule: Dict[str, Any], user_id: Optional[str] = None) -> None:
    """Save content schedule to JSON"""
    if user_id:
        from core.auth import get_user_data_dir
        user_dir = get_user_data_dir(user_id)
        schedule_file = user_dir / "content_schedule.json"
    else:
        schedule_file = config.CONTENT_SCHEDULE_FILE
    
    with open(schedule_file, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)


def generate_monthly_posts(
    count: int = 30,
    external_signals: Optional[str] = None,
    start_date: Optional[str] = None,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate posts for a month
    
    Args:
        count: Number of posts to generate
        external_signals: Analysis from Feature 1
        start_date: Start date (YYYY-MM-DD), defaults to today
        user_id: User ID for user-specific persona state
    
    Returns:
        List of post dictionaries with scheduling info
    """
    persona_state = load_persona_state(user_id)
    
    # Generate posts using AI
    posts = generate_posts(count, external_signals, user_id)
    
    # Add scheduling information
    if not start_date:
        start_date = datetime.now().date()
    else:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    
    # Get posting preferences
    posts_per_day = persona_state["energy_cadence"]["posts_per_day_tolerance"]
    preferred_times = persona_state["energy_cadence"]["preferred_posting_times"]
    
    # Distribute posts across days
    scheduled_posts = []
    current_date = start_date
    posts_remaining = posts.copy()
    time_index = 0
    
    while posts_remaining and len(scheduled_posts) < count:
        # Schedule up to posts_per_day for this date
        posts_today = min(posts_per_day, len(posts_remaining))
        
        for i in range(posts_today):
            if not posts_remaining:
                break
            
            post = posts_remaining.pop(0)
            
            # Assign time
            if time_index < len(preferred_times):
                scheduled_time = preferred_times[time_index]
            else:
                # Distribute across day if more posts than preferred times
                hour = 9 + (i * 3)  # 9am, 12pm, 3pm, 6pm
                scheduled_time = f"{hour:02d}:00"
            
            scheduled_posts.append({
                **post,
                "scheduled_date": current_date.strftime("%Y-%m-%d"),
                "scheduled_time": scheduled_time,
                "status": "draft",
                "created_at": datetime.now().isoformat()
            })
        
        # Move to next day
        current_date += timedelta(days=1)
        time_index = (time_index + 1) % len(preferred_times) if preferred_times else 0
    
    return scheduled_posts


def add_posts_to_schedule(posts: List[Dict[str, Any]], user_id: Optional[str] = None) -> None:
    """Add generated posts to schedule"""
    schedule = load_content_schedule(user_id)
    schedule["posts"].extend(posts)
    save_content_schedule(schedule, user_id)


def get_scheduled_posts(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get scheduled posts within date range
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        List of scheduled posts
    """
    schedule = load_content_schedule(user_id)
    all_posts = schedule.get("posts", [])
    
    if not start_date and not end_date:
        return all_posts
    
    filtered = []
    for post in all_posts:
        post_date = post.get("scheduled_date")
        if not post_date:
            continue
        
        if start_date and post_date < start_date:
            continue
        if end_date and post_date > end_date:
            continue
        
        filtered.append(post)
    
    # Sort by date and time
    filtered.sort(key=lambda x: (x.get("scheduled_date", ""), x.get("scheduled_time", "")))
    
    return filtered


def update_post(
    post_id: str,
    updates: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update a scheduled post
    
    Args:
        post_id: Post ID
        updates: Dictionary of fields to update
        user_id: User ID
    
    Returns:
        Updated post dictionary
    """
    schedule = load_content_schedule(user_id)
    posts = schedule.get("posts", [])
    
    for i, post in enumerate(posts):
        if post.get("id") == post_id:
            # Track if content was edited for learning
            if "content" in updates and updates["content"] != post.get("content"):
                original_content = post.get("content", "")
                process_explicit_feedback("edit", updates["content"], original_content, user_id)
            
            # Update post
            posts[i].update(updates)
            save_content_schedule(schedule, user_id)
            return posts[i]
    
    return {"error": "Post not found"}


def delete_post(post_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete a scheduled post"""
    schedule = load_content_schedule(user_id)
    posts = schedule.get("posts", [])
    
    for i, post in enumerate(posts):
        if post.get("id") == post_id:
            deleted = posts.pop(i)
            save_content_schedule(schedule, user_id)
            
            # Learn from rejection
            process_explicit_feedback("rejection", post.get("content"), None, user_id)
            
            return {"deleted": deleted}
    
    return {"error": "Post not found"}


def get_posts_ready_to_post(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get posts that are scheduled and ready to post (scheduled time has passed)
    
    Args:
        user_id: User ID
    
    Returns:
        List of posts ready to post
    """
    schedule = load_content_schedule(user_id)
    posts = schedule.get("posts", [])
    
    from datetime import datetime
    now = datetime.now()
    ready_posts = []
    
    for post in posts:
        if post.get("status") == "approved" and post.get("scheduled_date") and post.get("scheduled_time"):
            try:
                scheduled_datetime_str = f"{post['scheduled_date']} {post['scheduled_time']}"
                scheduled_datetime = datetime.strptime(scheduled_datetime_str, "%Y-%m-%d %H:%M")
                
                if scheduled_datetime <= now and not post.get("posted"):
                    ready_posts.append(post)
            except:
                pass
    
    return ready_posts


def approve_post(post_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Approve a post (mark as ready to post)"""
    result = update_post(post_id, {"status": "approved"}, user_id)
    
    if "error" not in result:
        # Learn from approval
        process_explicit_feedback("approval", result.get("content"), None, user_id)
        update_from_feedback("engagement_behavior", {"action": "approval"}, user_id)
    
    return result


def get_post_rationale(post_id: str, user_id: Optional[str] = None) -> str:
    """Get explanation of why a post fits the persona"""
    schedule = load_content_schedule(user_id)
    posts = schedule.get("posts", [])
    
    for post in posts:
        if post.get("id") == post_id:
            content = post.get("content", "")
            rationale = post.get("rationale", "")
            
            # Generate enhanced rationale if needed
            if not rationale or rationale == "Generated based on persona profile":
                rationale = explain_persona_alignment(content, "post", user_id)
                update_post(post_id, {"rationale": rationale}, user_id)
            
            return rationale
    
    return "Post not found"

