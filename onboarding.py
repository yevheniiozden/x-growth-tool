"""Onboarding flow for initial Persona State setup"""
from typing import Dict, Any, Optional
from core.persona_state import load_persona_state, update_from_feedback, save_persona_state
from services.x_api import get_user_timeline, get_user_likes, get_user_replies
from services.ai_service import client
import json


def run_onboarding_phase1(username: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Phase 1: Passive Ingestion
    Pull last 30-60 days of activity and extract initial Persona State
    """
    state = load_persona_state(user_id)
    
    # Get user activity
    timeline = get_user_timeline(username, days_back=60, max_results=100)
    likes = get_user_likes(username, days_back=60, max_results=200)
    replies = get_user_replies(username, days_back=60, max_results=100)
    
    # Extract topic affinity from likes
    if likes and client:
        # Use AI to extract topics from liked posts
        liked_texts = [like.get("text", "") for like in likes[:50]]
        topics = _extract_topics_from_posts(liked_texts)
        
        # Update topic affinity
        for topic, weight in topics.items():
            if topic in state["topic_affinity"]:
                # Set initial weight based on frequency
                state["topic_affinity"][topic] = min(1.0, weight)
    
    # Extract tone from user's own posts
    if timeline:
        user_posts = [t.get("text", "") for t in timeline[:30]]
        tone_analysis = _analyze_tone_from_posts(user_posts)
        
        # Update tone style
        if tone_analysis.get("sentence_length"):
            state["tone_style"]["sentence_length"] = tone_analysis["sentence_length"]
        if tone_analysis.get("question_frequency") is not None:
            state["tone_style"]["question_frequency"] = tone_analysis["question_frequency"]
        if tone_analysis.get("formality"):
            state["tone_style"]["formality"] = tone_analysis["formality"]
    
    # Extract engagement behavior
    if replies:
        state["engagement_behavior"]["replies_per_day_baseline"] = len(replies) // 30  # Average per day
        state["engagement_behavior"]["replies_per_day_baseline"] = max(1, min(20, state["engagement_behavior"]["replies_per_day_baseline"]))
    
    if likes:
        state["engagement_behavior"]["likes_per_day_baseline"] = len(likes) // 30
        state["engagement_behavior"]["likes_per_day_baseline"] = max(5, min(100, state["engagement_behavior"]["likes_per_day_baseline"]))
    
    # Extract posting cadence
    if timeline:
        posts_per_day = len(timeline) / 60  # Over 60 days
        state["energy_cadence"]["posts_per_day_tolerance"] = max(1, min(5, int(posts_per_day)))
    
    # Save updated state
    save_persona_state(state, user_id)
    
    return {
        "completed": True,
        "phase": 1,
        "data_ingested": {
            "posts": len(timeline),
            "likes": len(likes),
            "replies": len(replies)
        },
        "persona_updated": True
    }


def _extract_topics_from_posts(posts: list) -> Dict[str, float]:
    """Extract topic weights from posts using AI"""
    if not client or not posts:
        return {}
    
    try:
        posts_text = "\n\n".join(posts[:30])
        
        prompt = f"""Analyze the following liked posts and determine topic affinity scores (0-1) for these topics:
- saas
- ai
- startups
- product
- distribution
- operations
- online_business
- money
- personal_reflections
- humor

Posts:
{posts_text}

Return JSON with topic names as keys and scores (0-1) as values. Only include topics that are clearly present.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You analyze social media content and extract topic affinities."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        print(f"Error extracting topics: {e}")
        return {}


def _analyze_tone_from_posts(posts: list) -> Dict[str, Any]:
    """Analyze tone characteristics from user's posts"""
    if not posts:
        return {}
    
    analysis = {}
    
    # Calculate average sentence length
    all_sentences = []
    for post in posts:
        sentences = post.split('.')
        all_sentences.extend([s.strip() for s in sentences if s.strip()])
    
    if all_sentences:
        avg_words = sum(len(s.split()) for s in all_sentences) / len(all_sentences)
        if avg_words < 10:
            analysis["sentence_length"] = "short"
        elif avg_words < 20:
            analysis["sentence_length"] = "medium"
        else:
            analysis["sentence_length"] = "long"
    
    # Calculate question frequency
    total_posts = len(posts)
    posts_with_questions = sum(1 for p in posts if '?' in p)
    analysis["question_frequency"] = posts_with_questions / total_posts if total_posts > 0 else 0.4
    
    # Simple formality detection (basic heuristic)
    formal_words = ['please', 'thank you', 'appreciate', 'regards']
    has_formal = any(word in ' '.join(posts).lower() for word in formal_words)
    analysis["formality"] = "formal" if has_formal else "casual"
    
    return analysis

