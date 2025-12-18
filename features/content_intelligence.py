"""Feature 1: List-Based Content Intelligence"""
from typing import List, Dict, Any, Optional
from services.x_api import get_list_timeline, get_list_members
from services.ai_service import analyze_content_patterns
from core.persona_state import load_persona_state


def analyze_list_content(
    list_id: str,
    days_back: int = 30,
    max_posts: int = 200
) -> Dict[str, Any]:
    """
    Analyze content from an X List
    
    Args:
        list_id: X List ID
        days_back: How many days back to analyze
        max_posts: Maximum posts to analyze
    
    Returns:
        Analysis report dictionary
    """
    # Load Persona State for filtering
    persona_state = load_persona_state()
    
    # Fetch posts from list
    posts = get_list_timeline(list_id, days_back, max_posts)
    
    if not posts:
        return {
            "error": "No posts found in list",
            "list_id": list_id
        }
    
    # Get list members for context
    members = get_list_members(list_id)
    
    # Analyze with AI (persona-aware)
    analysis_text = analyze_content_patterns(posts)
    
    # Extract basic stats
    total_posts = len(posts)
    total_accounts = len(members)
    
    # Calculate average post length
    post_lengths = [len(post["text"].split()) for post in posts]
    avg_length = sum(post_lengths) / len(post_lengths) if post_lengths else 0
    
    # Calculate engagement averages
    avg_likes = sum(p.get("metrics", {}).get("likes", 0) for p in posts) / total_posts if posts else 0
    avg_replies = sum(p.get("metrics", {}).get("replies", 0) for p in posts) / total_posts if posts else 0
    avg_retweets = sum(p.get("metrics", {}).get("retweets", 0) for p in posts) / total_posts if posts else 0
    
    return {
        "list_id": list_id,
        "analysis_date": posts[0]["created_at"] if posts else None,
        "summary": {
            "total_posts_analyzed": total_posts,
            "total_accounts": total_accounts,
            "time_range_days": days_back,
            "average_post_length": round(avg_length, 1),
            "average_engagement": {
                "likes": round(avg_likes, 1),
                "replies": round(avg_replies, 1),
                "retweets": round(avg_retweets, 1)
            }
        },
        "ai_analysis": analysis_text,
        "persona_alignment": {
            "top_topics": _extract_top_topics(analysis_text, persona_state),
            "tone_match": _assess_tone_match(analysis_text, persona_state)
        }
    }


def _extract_top_topics(analysis_text: str, persona_state: Dict[str, Any]) -> List[str]:
    """Extract top topics from analysis that align with persona"""
    # Simple extraction - in production, this would be more sophisticated
    topic_affinity = persona_state.get("topic_affinity", {})
    top_persona_topics = sorted(
        topic_affinity.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    return [topic for topic, _ in top_persona_topics]


def _assess_tone_match(analysis_text: str, persona_state: Dict[str, Any]) -> str:
    """Assess how well analyzed content matches persona tone"""
    # Simple heuristic - in production, would use AI
    tone_style = persona_state.get("tone_style", {})
    
    # Check for mentions of persona tone characteristics
    formality = tone_style.get("formality", "casual")
    if formality in analysis_text.lower():
        return "High match"
    else:
        return "Moderate match"


def analyze_multiple_lists(list_ids: List[str], days_back: int = 30) -> Dict[str, Any]:
    """
    Analyze content from multiple lists
    
    Args:
        list_ids: List of X List IDs
        days_back: Days back to analyze
    
    Returns:
        Combined analysis report
    """
    all_analyses = []
    
    for list_id in list_ids:
        analysis = analyze_list_content(list_id, days_back)
        if "error" not in analysis:
            all_analyses.append(analysis)
    
    if not all_analyses:
        return {"error": "No valid analyses generated"}
    
    # Combine summaries
    total_posts = sum(a["summary"]["total_posts_analyzed"] for a in all_analyses)
    total_accounts = sum(a["summary"]["total_accounts"] for a in all_analyses)
    
    # Combine AI analyses
    combined_analysis = "\n\n---\n\n".join([a["ai_analysis"] for a in all_analyses])
    
    return {
        "lists_analyzed": len(all_analyses),
        "combined_summary": {
            "total_posts_analyzed": total_posts,
            "total_accounts": total_accounts,
            "time_range_days": days_back
        },
        "combined_ai_analysis": combined_analysis,
        "individual_analyses": all_analyses
    }

