"""Main FastAPI application for X Growth AI Tool"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import features
from features.content_intelligence import analyze_list_content, analyze_multiple_lists
from features.content_machine import (
    generate_monthly_posts, add_posts_to_schedule, get_scheduled_posts,
    update_post, delete_post, approve_post, get_post_rationale
)
from features.daily_actions import (
    get_daily_targets, get_prioritized_actions, track_action,
    get_today_progress, sync_from_x_api
)
from features.reply_guy import process_reply_opportunities, get_pending_replies, mark_reply_used
from core.persona_state import load_persona_state, get_persona_explanation
from services.x_api import get_user_lists, get_current_user
from onboarding import run_onboarding_phase1

app = FastAPI(title="X Growth AI Tool", version="1.0.0")


# Pydantic models
class TrackActionRequest(BaseModel):
    action_type: str
    action_data: Dict[str, Any]
    action_date: Optional[str] = None


class UpdatePostRequest(BaseModel):
    content: Optional[str] = None
    scheduled_date: Optional[str] = None
    scheduled_time: Optional[str] = None
    status: Optional[str] = None


class ReplyCheckRequest(BaseModel):
    list_ids: List[str]


# Root route - serve web UI
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web UI"""
    from pathlib import Path
    html_file = Path(__file__).parent / "templates" / "index.html"
    with open(html_file, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())


# Persona State API
@app.get("/api/persona/state")
async def get_persona_state():
    """Get current Persona State"""
    return load_persona_state()


@app.get("/api/persona/explanation")
async def get_persona_explanation_endpoint():
    """Get human-readable Persona State explanation"""
    from fastapi.responses import PlainTextResponse
    explanation = get_persona_explanation()
    return PlainTextResponse(content=explanation)


# Content Intelligence API
@app.get("/api/content-intelligence/analyze/{list_id}")
async def analyze_list_endpoint(list_id: str, days_back: int = 30):
    """Analyze content from an X List"""
    try:
        result = analyze_list_content(list_id, days_back)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/content-intelligence/analyze-multiple")
async def analyze_multiple_lists_endpoint(list_ids: List[str], days_back: int = 30):
    """Analyze content from multiple lists"""
    try:
        result = analyze_multiple_lists(list_ids, days_back)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Content Machine API
@app.post("/api/content-machine/generate")
async def generate_posts_endpoint(count: int = 30, external_signals: Optional[str] = None):
    """Generate monthly posts"""
    try:
        posts = generate_monthly_posts(count, external_signals)
        # Filter out any error posts
        valid_posts = [p for p in posts if "error" not in p]
        if valid_posts:
            add_posts_to_schedule(valid_posts)
        return {"count": len(valid_posts), "posts": valid_posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content-machine/schedule")
async def get_schedule_endpoint(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get scheduled posts"""
    try:
        posts = get_scheduled_posts(start_date, end_date)
        return posts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content-machine/posts/{post_id}")
async def get_post_endpoint(post_id: str):
    """Get a specific post"""
    schedule = get_scheduled_posts()
    for post in schedule:
        if post.get("id") == post_id:
            return post
    raise HTTPException(status_code=404, detail="Post not found")


@app.put("/api/content-machine/posts/{post_id}")
async def update_post_endpoint(post_id: str, updates: UpdatePostRequest):
    """Update a scheduled post"""
    try:
        update_dict = updates.dict(exclude_unset=True)
        result = update_post(post_id, update_dict)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/content-machine/posts/{post_id}")
async def delete_post_endpoint(post_id: str):
    """Delete a scheduled post"""
    try:
        result = delete_post(post_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/content-machine/posts/{post_id}/approve")
async def approve_post_endpoint(post_id: str):
    """Approve a post"""
    try:
        result = approve_post(post_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content-machine/posts/{post_id}/rationale")
async def get_post_rationale_endpoint(post_id: str):
    """Get rationale for why a post fits persona"""
    try:
        rationale = get_post_rationale(post_id)
        return {"rationale": rationale}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Daily Actions API
@app.get("/api/daily-actions/targets")
async def get_targets_endpoint(target_date: Optional[str] = None):
    """Get daily action targets"""
    try:
        return get_daily_targets(target_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/daily-actions/prioritized")
async def get_prioritized_endpoint(target_date: Optional[str] = None):
    """Get prioritized actions"""
    try:
        return get_prioritized_actions(target_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/daily-actions/progress")
async def get_progress_endpoint(target_date: Optional[str] = None):
    """Get today's progress"""
    try:
        return get_today_progress(target_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/daily-actions/track")
async def track_action_endpoint(request: TrackActionRequest):
    """Track a completed action"""
    try:
        return track_action(request.action_type, request.action_data, request.action_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/daily-actions/sync")
async def sync_actions_endpoint(username: Optional[str] = None):
    """Sync actions from X API"""
    try:
        return sync_from_x_api(username)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Reply Guy API
@app.post("/api/reply-guy/check")
async def check_replies_endpoint(request: ReplyCheckRequest):
    """Check for reply opportunities"""
    try:
        result = process_reply_opportunities(request.list_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reply-guy/pending")
async def get_pending_replies_endpoint():
    """Get pending reply opportunities"""
    try:
        return get_pending_replies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reply-guy/mark-used/{post_id}")
async def mark_reply_used_endpoint(post_id: str, reply_content: Optional[str] = None):
    """Mark a reply as used"""
    try:
        if not reply_content:
            raise HTTPException(status_code=400, detail="reply_content parameter required")
        return mark_reply_used(post_id, reply_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# X API Integration
@app.get("/api/x/lists")
async def get_x_lists_endpoint(username: Optional[str] = None):
    """Get user's X Lists"""
    try:
        lists = get_user_lists(username)
        return {"lists": lists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/x/user")
async def get_x_user_endpoint():
    """Get current authenticated user"""
    try:
        user = get_current_user()
        if not user:
            raise HTTPException(status_code=404, detail="User not authenticated")
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Onboarding API
@app.get("/api/onboarding/status")
async def onboarding_status_endpoint():
    """Check if onboarding has been completed"""
    try:
        state = load_persona_state()
        has_onboarding = (
            state.get("learning_history", {}).get("last_updated") is not None or
            state.get("learning_history", {}).get("total_approvals", 0) > 0
        )
        return {
            "onboarding_complete": has_onboarding,
            "last_updated": state.get("learning_history", {}).get("last_updated")
        }
    except Exception as e:
        return {"onboarding_complete": False, "error": str(e)}


@app.post("/api/onboarding/phase1")
async def onboarding_phase1_endpoint(username: Optional[str] = None):
    """Run Phase 1 onboarding (passive ingestion)"""
    try:
        result = run_onboarding_phase1(username)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

