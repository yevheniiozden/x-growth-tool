"""Step-by-step onboarding flow with X account connection"""
from typing import Dict, Any, Optional
from core.persona_state import load_persona_state, save_persona_state
from core.auth import update_user, get_user_data_dir
from services.x_api import get_user_timeline, get_user_likes, get_user_replies, get_current_user
from services.ai_service import client
import json


def get_onboarding_step(user_id: str) -> Dict[str, Any]:
    """Get current onboarding step for user"""
    from core.auth import load_users
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
        "message": _get_step_message(step, x_connected)
    }


def _get_step_message(step: int, x_connected: bool) -> str:
    """Get message for current step"""
    messages = {
        1: "Welcome! Let's connect your X account to get started.",
        2: "Great! Now we'll analyze your X activity to understand your persona.",
        3: "Perfect! Your persona is being created. This will take a few moments...",
        4: "Onboarding complete! Your AI brain is ready."
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
    from core.auth import load_users, save_users
    
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


def run_persona_analysis(user_id: str) -> Dict[str, Any]:
    """
    Step 2: Analyze user's X activity and create persona
    
    Args:
        user_id: User ID
    
    Returns:
        Result dict
    """
    from core.auth import load_users, save_users
    from onboarding import run_onboarding_phase1
    
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    user = users[user_id]
    x_username = user.get("x_username")
    
    if not x_username:
        return {"success": False, "error": "X account not connected"}
    
    try:
        # Run onboarding phase 1
        result = run_onboarding_phase1(x_username, user_id)
        
        if result.get("completed"):
            # Update user progress
            users[user_id]["onboarding_step"] = 3
            users[user_id]["onboarding_complete"] = True
            save_users(users)
            
            return {
                "success": True,
                "message": "Persona analysis complete!",
                "step": 3,
                "data_ingested": result.get("data_ingested", {})
            }
        else:
            return {
                "success": False,
                "error": "Persona analysis failed"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error during analysis: {str(e)}"
        }


def complete_onboarding(user_id: str) -> Dict[str, Any]:
    """Mark onboarding as complete"""
    from core.auth import load_users, save_users
    
    users = load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found"}
    
    users[user_id]["onboarding_complete"] = True
    users[user_id]["onboarding_step"] = 4
    save_users(users)
    
    return {
        "success": True,
        "message": "Onboarding complete!",
        "step": "complete"
    }

