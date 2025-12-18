"""Feature 3: Reply Guy Engine"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from services.x_api import get_list_timeline, get_list_members
from services.ai_service import generate_reply_suggestions
from services.telegram_bot import send_reply_notification
from core.persona_state import load_persona_state
import config


def load_reply_tracking() -> Dict[str, Any]:
    """Load reply tracking data"""
    tracking_file = config.DATA_DIR / "reply_tracking.json"
    if tracking_file.exists():
        try:
            with open(tracking_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"tracked_posts": {}, "last_check": None}
    return {"tracked_posts": {}, "last_check": None}


def save_reply_tracking(tracking: Dict[str, Any]) -> None:
    """Save reply tracking data"""
    tracking_file = config.DATA_DIR / "reply_tracking.json"
    with open(tracking_file, 'w', encoding='utf-8') as f:
        json.dump(tracking, f, indent=2, ensure_ascii=False)


def monitor_list_accounts(list_id: str, hours_back: int = 24) -> List[Dict[str, Any]]:
    """
    Monitor accounts in a list for new posts
    
    Args:
        list_id: X List ID
        hours_back: How many hours back to check
    
    Returns:
        List of new posts with reply suggestions
    """
    tracking = load_reply_tracking()
    tracked_post_ids = set(tracking.get("tracked_posts", {}).keys())
    
    # Get recent posts from list
    days_back = max(1, hours_back // 24)
    posts = get_list_timeline(list_id, days_back=days_back, max_results=50)
    
    # Filter for new posts (not yet tracked)
    new_posts = [
        p for p in posts
        if p["id"] not in tracked_post_ids
    ]
    
    # Filter by time (last N hours)
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    recent_posts = [
        p for p in new_posts
        if p.get("created_at") and datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) >= cutoff_time
    ]
    
    # Generate reply suggestions for each
    reply_opportunities = []
    persona_state = load_persona_state()
    
    for post in recent_posts:
        # Generate reply suggestions
        suggestions = generate_reply_suggestions(post, count=3)
        
        # Filter through persona (risk tolerance, tone)
        filtered_suggestions = _filter_by_persona(suggestions, persona_state)
        
        if filtered_suggestions:
            reply_opportunities.append({
                "post_id": post["id"],
                "original_post": post,
                "suggestions": filtered_suggestions,
                "created_at": post.get("created_at"),
                "list_id": list_id
            })
            
            # Mark as tracked
            tracking["tracked_posts"][post["id"]] = {
                "tracked_at": datetime.now().isoformat(),
                "list_id": list_id
            }
    
    tracking["last_check"] = datetime.now().isoformat()
    save_reply_tracking(tracking)
    
    return reply_opportunities


def _filter_by_persona(
    suggestions: List[Dict[str, Any]],
    persona_state: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Filter reply suggestions through persona state"""
    risk_sensitivity = persona_state.get("risk_sensitivity", {})
    challenge_tendency = risk_sensitivity.get("challenge_others_tendency", 0.5)
    
    filtered = []
    for suggestion in suggestions:
        angle = suggestion.get("angle", "extend")
        
        # Filter out challenges if risk tolerance is low
        if angle == "challenge" and challenge_tendency < 0.3:
            continue  # Skip aggressive challenges if user is risk-averse
        
        filtered.append(suggestion)
    
    return filtered


def get_pending_replies() -> List[Dict[str, Any]]:
    """Get all pending reply opportunities"""
    # This would load from a queue or database
    # For now, return empty list (would be populated by monitoring)
    pending_file = config.DATA_DIR / "pending_replies.json"
    if pending_file.exists():
        try:
            with open(pending_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_pending_reply(opportunity: Dict[str, Any]) -> None:
    """Save a reply opportunity to pending queue"""
    pending = get_pending_replies()
    pending.append(opportunity)
    
    pending_file = config.DATA_DIR / "pending_replies.json"
    with open(pending_file, 'w', encoding='utf-8') as f:
        json.dump(pending, f, indent=2, ensure_ascii=False)


def process_reply_opportunities(list_ids: List[str]) -> Dict[str, Any]:
    """
    Process reply opportunities for multiple lists and send notifications
    
    Args:
        list_ids: List of X List IDs to monitor
    
    Returns:
        Processing results
    """
    all_opportunities = []
    
    for list_id in list_ids:
        opportunities = monitor_list_accounts(list_id)
        all_opportunities.extend(opportunities)
    
    # Send Telegram notifications
    notifications_sent = 0
    for opportunity in all_opportunities:
        try:
            send_reply_notification(opportunity)
            save_pending_reply(opportunity)
            notifications_sent += 1
        except Exception as e:
            print(f"Error sending notification: {e}")
    
    return {
        "opportunities_found": len(all_opportunities),
        "notifications_sent": notifications_sent,
        "lists_processed": len(list_ids)
    }


def mark_reply_used(post_id: str, reply_content: str) -> Dict[str, Any]:
    """
    Mark a reply as used (user posted it)
    
    Args:
        post_id: Original post ID
        reply_content: Reply content that was used
    
    Returns:
        Confirmation
    """
    pending = get_pending_replies()
    
    # Remove from pending
    updated_pending = [
        p for p in pending
        if p.get("post_id") != post_id
    ]
    
    pending_file = config.DATA_DIR / "pending_replies.json"
    with open(pending_file, 'w', encoding='utf-8') as f:
        json.dump(updated_pending, f, indent=2, ensure_ascii=False)
    
    # Learn from reply choice
    from core.learning_loop import process_explicit_feedback
    process_explicit_feedback("approval", reply_content)
    
    return {
        "marked": True,
        "post_id": post_id
    }

