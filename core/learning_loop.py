"""Learning Loop - Processes feedback to update Persona State"""
from typing import Dict, Any, Optional
from datetime import datetime
from core.persona_state import load_persona_state, update_from_feedback


def process_explicit_feedback(
    action: str,
    content: Optional[str] = None,
    original_content: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process explicit feedback: edits, approvals, rejections
    
    Args:
        action: 'approval', 'rejection', 'edit'
        content: Final content (if edit or approval)
        original_content: Original content (if edit)
        user_id: User ID for user-specific persona state
    """
    state = load_persona_state(user_id)
    updates = []
    
    if action == "approval":
        # User approved content - learn from what they kept
        update_from_feedback("engagement_behavior", {
            "action": "approval"
        }, user_id)
        updates.append("Learned from approved content")
    
    elif action == "rejection":
        # User rejected content - learn what to avoid
        update_from_feedback("engagement_behavior", {
            "action": "rejection"
        }, user_id)
        updates.append("Learned from rejected content")
    
    elif action == "edit" and content and original_content:
        # User edited content - learn from changes
        # Analyze differences to infer tone/style preferences
        original_length = len(original_content.split())
        edited_length = len(content.split())
        
        # Learn from length changes
        if edited_length < original_length * 0.8:
            # User shortened - prefer concise
            update_from_feedback("tone_style", {
                "attribute": "sentence_length",
                "adjustment": -0.05
            }, user_id)
            updates.append("Learned: prefer shorter content")
        elif edited_length > original_length * 1.2:
            # User expanded - prefer detailed
            update_from_feedback("tone_style", {
                "attribute": "sentence_length",
                "adjustment": 0.05
            }, user_id)
            updates.append("Learned: prefer longer content")
        
        # Check for question additions/removals
        original_questions = original_content.count('?')
        edited_questions = content.count('?')
        if edited_questions > original_questions:
            update_from_feedback("tone_style", {
                "attribute": "question_frequency",
                "adjustment": 0.05
            }, user_id)
            updates.append("Learned: prefer questions")
        elif edited_questions < original_questions:
            update_from_feedback("tone_style", {
                "attribute": "question_frequency",
                "adjustment": -0.05
            }, user_id)
            updates.append("Learned: prefer fewer questions")
        
        update_from_feedback("engagement_behavior", {
            "action": "edit"
        }, user_id)
    
    return {
        "processed": True,
        "updates": updates,
        "action": action
    }


def process_behavioral_feedback(
    action_type: str,
    target_content: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process behavioral feedback: likes, replies, follows
    
    Args:
        action_type: 'like', 'reply', 'follow', 'retweet'
        target_content: Content that was engaged with (optional)
        user_id: User ID for user-specific persona state
    """
    updates = []
    
    if action_type == "like":
        # User liked something - learn topic affinity
        if target_content and "topics" in target_content:
            for topic in target_content["topics"]:
                update_from_feedback("topic_affinity", {
                    "topic": topic,
                    "adjustment": 0.02  # Small positive adjustment
                }, user_id)
            updates.append(f"Learned topic affinity from like")
    
    elif action_type == "reply":
        # User replied - learn engagement behavior
        update_from_feedback("engagement_behavior", {
            "attribute": "replies_per_day_baseline",
            "adjustment": 0.1  # Small increase
        }, user_id)
        updates.append("Learned engagement behavior from reply")
    
    elif action_type == "follow":
        # User followed after engagement
        update_from_feedback("engagement_behavior", {
            "attribute": "follow_after_reply_tendency",
            "adjustment": 0.05
        }, user_id)
        updates.append("Learned follow tendency")
    
    return {
        "processed": True,
        "updates": updates,
        "action_type": action_type
    }


def process_temporal_feedback(
    action: str,
    time_taken: Optional[float] = None,
    hesitation_signals: Optional[list] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process temporal feedback: speed of actions, hesitation
    
    Args:
        action: Action taken
        time_taken: Time in seconds
        hesitation_signals: List of hesitation indicators
        user_id: User ID for user-specific persona state
    """
    updates = []
    
    if hesitation_signals:
        # User hesitated or skipped - fatigue signal
        update_from_feedback("energy_cadence", {
            "attribute": "fatigue_signal",
            "signal": f"{action}_hesitation"
        }, user_id)
        updates.append("Detected engagement fatigue")
    
    if time_taken and time_taken > 300:  # More than 5 minutes
        # User took long - might indicate complexity or hesitation
        update_from_feedback("energy_cadence", {
            "attribute": "fatigue_signal",
            "signal": f"{action}_long_time"
        }, user_id)
        updates.append("Detected long processing time")
    
    return {
        "processed": True,
        "updates": updates,
        "action": action
    }


def process_outcome_feedback(
    post_id: str,
    engagement_metrics: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process outcome feedback: performance vs personal baseline
    
    Args:
        post_id: ID of the post
        engagement_metrics: Dict with likes, replies, retweets, etc.
        user_id: User ID for user-specific persona state
    """
    state = load_persona_state(user_id)
    updates = []
    
    # This would typically compare against user's historical baseline
    # For now, we'll do simple adjustments based on relative performance
    
    likes = engagement_metrics.get("likes", 0)
    replies = engagement_metrics.get("replies", 0)
    retweets = engagement_metrics.get("retweets", 0)
    
    # Simple heuristic: if engagement is above average, learn from topics
    # In a real implementation, this would compare against actual baseline
    total_engagement = likes + replies * 2 + retweets * 3
    
    if total_engagement > 50:  # Threshold - would be dynamic in real system
        # Post performed well - learn from it
        # This would need topic extraction from the post
        # For now, just log it
        updates.append("Post performed well - learning from topics")
    
    return {
        "processed": True,
        "updates": updates,
        "post_id": post_id,
        "engagement": total_engagement
    }


def process_onboarding_response(
    phase: int,
    response: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process response from interactive onboarding and update persona state
    
    Args:
        phase: Phase number (1-4)
        response: Response dictionary with post_id, account_id, response_type, response_value
        user_id: User ID
    
    Returns:
        Update summary
    """
    from services.ai_service import extract_topics_from_text, analyze_tone
    
    state = load_persona_state(user_id)
    updates = []
    
    post_id = response.get("post_id")
    account_id = response.get("account_id")
    response_type = response.get("response_type")
    response_value = response.get("response_value")
    
    # Phase 1: Content Like (Yes/No)
    if phase == 1:
        if response_value in [True, "yes", "Yes"]:
            # User likes this content - extract topics and tone
            # We need post text - this should be passed in response or fetched
            post_text = response.get("post_text", "")
            if post_text:
                # Extract topics
                topics = extract_topics_from_text(post_text)
                for topic, weight in topics.items():
                    if topic in state["topic_affinity"]:
                        # Incremental update
                        current = state["topic_affinity"][topic]
                        state["topic_affinity"][topic] = min(1.0, current + 0.02)
                        updates.append(f"Increased affinity for {topic}")
                
                # Analyze tone
                tone = analyze_tone(post_text)
                if tone:
                    # Update tone preferences incrementally
                    if "sentence_length" in tone:
                        # Prefer similar sentence length
                        current_length = state["tone_style"]["sentence_length"]
                        if tone["sentence_length"] == "short" and current_length != "short":
                            # Slight adjustment toward shorter
                            pass  # Would need more sophisticated logic
                    updates.append("Learned tone preferences")
        else:
            # User doesn't like - slight negative adjustment
            post_text = response.get("post_text", "")
            if post_text:
                topics = extract_topics_from_text(post_text)
                for topic in topics:
                    if topic in state["topic_affinity"]:
                        current = state["topic_affinity"][topic]
                        state["topic_affinity"][topic] = max(0.0, current - 0.01)
                        updates.append(f"Decreased affinity for {topic}")
    
    # Phase 2: Engagement (Yes/No)
    elif phase == 2:
        if response_value in [True, "yes", "Yes"]:
            # User would engage - learn engagement triggers
            post_text = response.get("post_text", "")
            if post_text:
                # Analyze what makes them want to engage
                # Check for questions, controversial topics, etc.
                if "?" in post_text:
                    state["tone_style"]["question_frequency"] = min(1.0, 
                        state["tone_style"]["question_frequency"] + 0.02)
                    updates.append("Increased preference for questions")
                
                # Update engagement behavior
                update_from_feedback("engagement_behavior", {
                    "attribute": "replies_per_day_baseline",
                    "adjustment": 0.1
                }, user_id)
                updates.append("Learned engagement triggers")
        else:
            # User wouldn't engage - learn what to avoid
            update_from_feedback("engagement_behavior", {
                "attribute": "replies_per_day_baseline",
                "adjustment": -0.05
            }, user_id)
            updates.append("Learned what not to engage with")
    
    # Phase 3: Like/Skip
    elif phase == 3:
        if response_type == "like" or response_value in [True, "like", "Like"]:
            # User likes - similar to phase 1
            post_text = response.get("post_text", "")
            if post_text:
                topics = extract_topics_from_text(post_text)
                for topic, weight in topics.items():
                    if topic in state["topic_affinity"]:
                        current = state["topic_affinity"][topic]
                        state["topic_affinity"][topic] = min(1.0, current + 0.015)
                        updates.append(f"Refined affinity for {topic}")
        else:
            # User skips - negative adjustment
            post_text = response.get("post_text", "")
            if post_text:
                topics = extract_topics_from_text(post_text)
                for topic in topics:
                    if topic in state["topic_affinity"]:
                        current = state["topic_affinity"][topic]
                        state["topic_affinity"][topic] = max(0.0, current - 0.01)
                        updates.append(f"Reduced affinity for {topic}")
    
    # Phase 4: Subscribe (Yes/No)
    elif phase == 4:
        if response_value in [True, "yes", "Yes", "subscribe", "Subscribe"]:
            # User would subscribe - learn account preferences
            account_description = response.get("account_description", "")
            if account_description:
                topics = extract_topics_from_text(account_description)
                for topic, weight in topics.items():
                    if topic in state["topic_affinity"]:
                        current = state["topic_affinity"][topic]
                        state["topic_affinity"][topic] = min(1.0, current + 0.02)
                        updates.append(f"Increased affinity for {topic} from account")
            
            # Update follow behavior
            update_from_feedback("engagement_behavior", {
                "attribute": "follow_after_reply_tendency",
                "adjustment": 0.05
            }, user_id)
            updates.append("Learned account preferences")
        else:
            # User wouldn't subscribe - learn what accounts to avoid
            updates.append("Learned account preferences to avoid")
    
    # Save updated state
    from core.persona_state import save_persona_state
    save_persona_state(state, user_id)
    
    return {
        "updated": True,
        "updates": updates,
        "state": state
    }


def process_daily_summary(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Process all feedback from the day and update Persona State"""
    # This would aggregate all feedback from the day
    # For now, just return summary
    state = load_persona_state(user_id)
    
    return {
        "processed": True,
        "summary": {
            "approvals": state["learning_history"]["total_approvals"],
            "rejections": state["learning_history"]["total_rejections"],
            "edits": state["learning_history"]["total_edits"],
            "last_updated": state["learning_history"].get("last_updated")
        }
    }

