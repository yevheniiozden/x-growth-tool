"""Main FastAPI application for X Growth AI Tool"""
from fastapi import FastAPI, HTTPException, Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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
from core.auth import (
    register_user, login_user, get_user_from_session,
    update_user, get_user_data_dir
)
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


# Helper function to get current user from request
async def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from session token in cookie or header"""
    session_token = None
    
    # Try cookie first
    if hasattr(request, 'cookies') and 'session_token' in request.cookies:
        session_token = request.cookies.get('session_token')
    
    # Try header
    if not session_token:
        session_token = request.headers.get('X-Session-Token')
    
    if session_token:
        return get_user_from_session(session_token)
    return None


# Auth routes
@app.get("/auth", response_class=HTMLResponse)
async def auth_page():
    """Serve authentication page"""
    from pathlib import Path
    html_file = Path(__file__).parent / "templates" / "auth.html"
    with open(html_file, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())


@app.post("/api/auth/register")
async def register_endpoint(request: Request):
    """Register a new user"""
    try:
        data = await request.json()
        result = register_user(
            email=data.get("email"),
            password=data.get("password"),
            username=data.get("username")
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/login")
async def login_endpoint(request: Request):
    """Login user"""
    try:
        data = await request.json()
        result = login_user(
            email=data.get("email"),
            password=data.get("password")
        )
        if result.get("success"):
            response = JSONResponse(result)
            response.set_cookie(
                key="session_token",
                value=result["session_token"],
                max_age=30*24*60*60,  # 30 days
                httponly=True,
                samesite="lax"
            )
            return response
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/logout")
async def logout_endpoint(request: Request):
    """Logout user"""
    response = JSONResponse({"success": True})
    response.delete_cookie("session_token")
    return response


@app.get("/api/auth/me")
async def get_current_user_endpoint(request: Request):
    """Get current authenticated user"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "user_id": user.get("user_id"),
        "username": user.get("username"),
        "email": user.get("email"),
        "x_connected": user.get("x_connected", False),
        "onboarding_complete": user.get("onboarding_complete", False),
        "onboarding_step": user.get("onboarding_step", 1)
    }


# Root route - serve web UI (with auth check)
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main web UI"""
    user = await get_current_user_from_request(request)
    
    # Redirect to auth if not logged in
    if not user:
        return RedirectResponse(url="/auth")
    
    from pathlib import Path
    html_file = Path(__file__).parent / "templates" / "index.html"
    with open(html_file, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())


# Persona State API
@app.get("/api/persona/state")
async def get_persona_state_endpoint(request: Request):
    """Get current Persona State"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return load_persona_state(user.get("user_id"))


@app.get("/api/persona/explanation")
async def get_persona_explanation_endpoint(request: Request):
    """Get human-readable Persona State explanation"""
    from fastapi.responses import PlainTextResponse
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    explanation = get_persona_explanation(user.get("user_id"))
    return PlainTextResponse(content=explanation)


# Content Intelligence API
@app.get("/api/content-intelligence/analyze/{list_id}")
async def analyze_list_endpoint(request: Request, list_id: str, days_back: int = 30):
    """Analyze content from an X List"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        result = analyze_list_content(list_id, days_back, user_id=user.get("user_id"))
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
async def generate_posts_endpoint(request: Request, count: int = 30, external_signals: Optional[str] = None):
    """Generate monthly posts"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        posts = generate_monthly_posts(count, external_signals, user.get("user_id"))
        # Filter out any error posts
        valid_posts = [p for p in posts if "error" not in p]
        if valid_posts:
            add_posts_to_schedule(valid_posts, user.get("user_id"))
        return {"count": len(valid_posts), "posts": valid_posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content-machine/schedule")
async def get_schedule_endpoint(request: Request, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get scheduled posts"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        posts = get_scheduled_posts(start_date, end_date, user.get("user_id"))
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
async def update_post_endpoint(request: Request, post_id: str, updates: UpdatePostRequest):
    """Update a scheduled post"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        update_dict = updates.dict(exclude_unset=True)
        result = update_post(post_id, update_dict, user.get("user_id"))
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/content-machine/posts/{post_id}")
async def delete_post_endpoint(request: Request, post_id: str):
    """Delete a scheduled post"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        result = delete_post(post_id, user.get("user_id"))
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/content-machine/posts/{post_id}/approve")
async def approve_post_endpoint(request: Request, post_id: str):
    """Approve a post"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        result = approve_post(post_id, user.get("user_id"))
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content-machine/posts/{post_id}/rationale")
async def get_post_rationale_endpoint(request: Request, post_id: str):
    """Get rationale for why a post fits persona"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        rationale = get_post_rationale(post_id, user.get("user_id"))
        return {"rationale": rationale}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Daily Actions API
@app.get("/api/daily-actions/targets")
async def get_targets_endpoint(request: Request, target_date: Optional[str] = None):
    """Get daily action targets"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return get_daily_targets(target_date, user.get("user_id"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/daily-actions/prioritized")
async def get_prioritized_endpoint(request: Request, target_date: Optional[str] = None):
    """Get prioritized actions"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return get_prioritized_actions(target_date, user.get("user_id"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/daily-actions/progress")
async def get_progress_endpoint(request: Request, target_date: Optional[str] = None):
    """Get today's progress"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return get_today_progress(target_date, user.get("user_id"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/daily-actions/track")
async def track_action_endpoint(request: Request, action_request: TrackActionRequest):
    """Track a completed action"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return track_action(
            action_request.action_type, 
            action_request.action_data, 
            action_request.action_date,
            user.get("user_id")
        )
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
async def onboarding_status_endpoint(request: Request):
    """Check onboarding status for current user"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from onboarding_flow import get_onboarding_step
    return get_onboarding_step(user.get("user_id"))


@app.get("/api/onboarding/step")
async def get_onboarding_step_endpoint(request: Request):
    """Get current onboarding step"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from onboarding_flow import get_onboarding_step
    return get_onboarding_step(user.get("user_id"))


@app.post("/api/onboarding/connect-x")
async def connect_x_endpoint(request: Request):
    """Step 1: Connect X account"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        x_username = data.get("x_username", "").strip().replace("@", "")
        
        if not x_username:
            raise HTTPException(status_code=400, detail="X username required")
        
        from onboarding_flow import connect_x_account
        result = connect_x_account(user.get("user_id"), x_username)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/analyze")
async def analyze_persona_endpoint(request: Request):
    """Step 2: Analyze persona from X activity"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        from onboarding_flow import run_persona_analysis
        result = run_persona_analysis(user.get("user_id"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/complete")
async def complete_onboarding_endpoint(request: Request):
    """Complete onboarding"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        from onboarding_flow import complete_onboarding
        result = complete_onboarding(user.get("user_id"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/phase1")
async def onboarding_phase1_endpoint(request: Request, username: Optional[str] = None):
    """Run Phase 1 onboarding (passive ingestion) - Legacy endpoint"""
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Use user's X username if available
    if not username:
        username = user.get("x_username")
    
    try:
        result = run_onboarding_phase1(username)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

