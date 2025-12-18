"""Feature 5: Daily Actions - 'What Should I Do Today?' Dashboard"""
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from core.persona_state import load_persona_state, update_from_feedback
from core.learning_loop import process_behavioral_feedback, process_temporal_feedback
from features.content_machine import get_scheduled_posts
from features.reply_guy import get_pending_replies
from services.x_api import get_user_timeline, get_user_likes, get_user_replies
import config


def load_activity_log() -> Dict[str, Any]:
    """Load activity log from JSON"""
    if config.ACTIVITY_LOG_FILE.exists():
        try:
            with open(config.ACTIVITY_LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"daily_activities": {}}
    return {"daily_activities": {}}


def save_activity_log(log: Dict[str, Any]) -> None:
    """Save activity log to JSON"""
    with open(config.ACTIVITY_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def get_daily_targets(target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate daily action targets
    
    Args:
        target_date: Date in YYYY-MM-DD format (defaults to today)
    
    Returns:
        Dictionary with targets and rationale
    """
    persona_state = load_persona_state()
    activity_log = load_activity_log()
    
    if not target_date:
        target_date = date.today().isoformat()
    
    # Get yesterday's activity
    yesterday = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).date().isoformat()
    yesterday_activity = activity_log.get("daily_activities", {}).get(yesterday, {})
    
    # Base targets from persona
    base_targets = {
        "posts": persona_state["energy_cadence"]["posts_per_day_tolerance"],
        "replies": persona_state["engagement_behavior"]["replies_per_day_baseline"],
        "likes": persona_state["engagement_behavior"]["likes_per_day_baseline"],
        "follows": 0  # Optional, not in persona
    }
    
    # Adjust based on yesterday
    yesterday_posts = yesterday_activity.get("posts", 0)
    yesterday_replies = yesterday_activity.get("replies", 0)
    yesterday_likes = yesterday_activity.get("likes", 0)
    
    # Check for fatigue signals
    fatigue_signals = persona_state["energy_cadence"].get("engagement_fatigue_signals", [])
    recent_fatigue = [
        s for s in fatigue_signals
        if datetime.fromisoformat(s["timestamp"]).date() >= (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=3)).date()
    ]
    
    # Adjust targets based on patterns
    targets = base_targets.copy()
    
    # If user did less yesterday, slightly increase today (momentum)
    if yesterday_posts < base_targets["posts"] * 0.5:
        targets["posts"] = max(1, base_targets["posts"] - 1)  # Reduce if very inactive
    
    # If fatigue signals, reduce targets
    if len(recent_fatigue) > 2:
        targets["posts"] = max(1, targets["posts"] - 1)
        targets["replies"] = max(1, int(targets["replies"] * 0.8))
    
    # Get available content
    scheduled_posts = get_scheduled_posts(target_date, target_date)
    available_posts = [p for p in scheduled_posts if p.get("status") in ["draft", "approved"]]
    
    # Get available replies
    available_replies = get_pending_replies()
    
    return {
        "date": target_date,
        "targets": targets,
        "available_content": {
            "posts": len(available_posts),
            "replies": len(available_replies)
        },
        "yesterday_activity": {
            "posts": yesterday_posts,
            "replies": yesterday_replies,
            "likes": yesterday_likes
        },
        "fatigue_signals": len(recent_fatigue),
        "rationale": _generate_target_rationale(targets, base_targets, recent_fatigue)
    }


def _generate_target_rationale(
    targets: Dict[str, int],
    base_targets: Dict[str, int],
    fatigue_signals: List[Dict[str, Any]]
) -> str:
    """Generate explanation for daily targets"""
    reasons = []
    
    if targets["posts"] < base_targets["posts"]:
        reasons.append(f"Reduced posts ({targets['posts']}) due to recent activity patterns")
    
    if fatigue_signals:
        reasons.append(f"Adjusted for {len(fatigue_signals)} recent fatigue signals")
    
    if not reasons:
        reasons.append("Targets based on your persona baseline")
    
    return "; ".join(reasons)


def get_prioritized_actions(target_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get prioritized action list for the day
    
    Args:
        target_date: Date in YYYY-MM-DD format
    
    Returns:
        List of prioritized actions
    """
    if not target_date:
        target_date = date.today().isoformat()
    
    actions = []
    
    # Get scheduled posts for today
    scheduled_posts = get_scheduled_posts(target_date, target_date)
    for post in scheduled_posts[:3]:  # Top 3
        if post.get("status") in ["draft", "approved"]:
            actions.append({
                "type": "post",
                "priority": 1,
                "action": f"Post: {post.get('content', '')[:50]}...",
                "data": post,
                "rationale": post.get("rationale", "Scheduled post")
            })
    
    # Get reply suggestions
    pending_replies = get_pending_replies()
    for reply in pending_replies[:5]:  # Top 5
        actions.append({
            "type": "reply",
            "priority": 2,
            "action": f"Reply to @{reply.get('author', 'user')}: {reply.get('original_post', {}).get('text', '')[:50]}...",
            "data": reply,
            "rationale": reply.get("rationale", "Engagement opportunity")
        })
    
    # Sort by priority
    actions.sort(key=lambda x: x["priority"])
    
    return actions


def track_action(
    action_type: str,
    action_data: Dict[str, Any],
    action_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Track a completed action
    
    Args:
        action_type: 'post', 'reply', 'like', 'follow'
        action_data: Action details
        action_date: Date (defaults to today)
    
    Returns:
        Confirmation dictionary
    """
    if not action_date:
        action_date = date.today().isoformat()
    
    activity_log = load_activity_log()
    
    if "daily_activities" not in activity_log:
        activity_log["daily_activities"] = {}
    
    if action_date not in activity_log["daily_activities"]:
        activity_log["daily_activities"][action_date] = {
            "posts": 0,
            "replies": 0,
            "likes": 0,
            "follows": 0,
            "actions": []
        }
    
    # Increment counter (handle plural forms)
    counter_key = f"{action_type}s" if action_type in ["post", "reply", "like", "follow"] else action_type
    if counter_key in activity_log["daily_activities"][action_date]:
        activity_log["daily_activities"][action_date][counter_key] += 1
    
    # Add action detail
    activity_log["daily_activities"][action_date]["actions"].append({
        "type": action_type,
        "timestamp": datetime.now().isoformat(),
        "data": action_data
    })
    
    save_activity_log(activity_log)
    
    # Process behavioral feedback
    process_behavioral_feedback(action_type, action_data)
    
    return {
        "tracked": True,
        "action_type": action_type,
        "date": action_date
    }


def get_today_progress(target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get progress for today's actions
    
    Args:
        target_date: Date (defaults to today)
    
    Returns:
        Progress dictionary
    """
    if not target_date:
        target_date = date.today().isoformat()
    
    targets = get_daily_targets(target_date)
    activity_log = load_activity_log()
    
    today_activity = activity_log.get("daily_activities", {}).get(target_date, {})
    
    progress = {
        "date": target_date,
        "targets": targets["targets"],
        "completed": {
            "posts": today_activity.get("posts", 0),
            "replies": today_activity.get("replies", 0),
            "likes": today_activity.get("likes", 0),
            "follows": today_activity.get("follows", 0)
        },
        "remaining": {
            "posts": max(0, targets["targets"]["posts"] - today_activity.get("posts", 0)),
            "replies": max(0, targets["targets"]["replies"] - today_activity.get("replies", 0)),
            "likes": max(0, targets["targets"]["likes"] - today_activity.get("likes", 0)),
            "follows": max(0, targets["targets"]["follows"] - today_activity.get("follows", 0))
        }
    }
    
    # Calculate completion percentage
    total_targets = sum(targets["targets"].values())
    total_completed = sum(progress["completed"].values())
    progress["completion_percentage"] = (total_completed / total_targets * 100) if total_targets > 0 else 0
    
    return progress


def sync_from_x_api(username: Optional[str] = None) -> Dict[str, Any]:
    """
    Sync today's activity from X API
    
    Args:
        username: Twitter username
    
    Returns:
        Sync results
    """
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    
    # Get today's timeline (posts)
    timeline = get_user_timeline(username, days_back=1, max_results=50)
    today_posts = [
        t for t in timeline
        if t.get("created_at") and datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")).date() == today
    ]
    
    # Get today's likes
    likes = get_user_likes(username, days_back=1, max_results=100)
    today_likes = [
        l for l in likes
        if l.get("created_at") and datetime.fromisoformat(l["created_at"].replace("Z", "+00:00")).date() == today
    ]
    
    # Get today's replies
    replies = get_user_replies(username, days_back=1, max_results=50)
    today_replies = [
        r for r in replies
        if r.get("created_at") and datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).date() == today
    ]
    
    # Track all actions
    for post in today_posts:
        track_action("post", {"post_id": post["id"], "text": post["text"]})
    
    for like in today_likes:
        track_action("like", {"tweet_id": like["id"]})
    
    for reply in today_replies:
        track_action("reply", {"reply_id": reply["id"], "text": reply["text"]})
    
    return {
        "synced": True,
        "posts": len(today_posts),
        "likes": len(today_likes),
        "replies": len(today_replies),
        "date": today.isoformat()
    }

