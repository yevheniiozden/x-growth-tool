"""Authentication system for multi-user support"""
import hashlib
import secrets
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import config

# User data directory
USERS_DIR = config.DATA_DIR / "users"
USERS_DIR.mkdir(exist_ok=True)

# Sessions storage
SESSIONS_FILE = config.DATA_DIR / "sessions.json"


def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_session_token() -> str:
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)


def load_sessions() -> Dict[str, Any]:
    """Load sessions from file"""
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_sessions(sessions: Dict[str, Any]) -> None:
    """Save sessions to file"""
    # Clean expired sessions
    now = datetime.now()
    active_sessions = {}
    for token, session_data in sessions.items():
        expires = datetime.fromisoformat(session_data.get("expires", "2000-01-01"))
        if expires > now:
            active_sessions[token] = session_data
    
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(active_sessions, f, indent=2, ensure_ascii=False)


def load_users() -> Dict[str, Any]:
    """Load users database"""
    users_file = USERS_DIR / "users.json"
    if users_file.exists():
        try:
            with open(users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_users(users: Dict[str, Any]) -> None:
    """Save users database"""
    users_file = USERS_DIR / "users.json"
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def register_user(email: str, password: str, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Register a new user
    
    Returns:
        Dict with 'success' and 'user_id' or 'error'
    """
    users = load_users()
    
    # Check if email already exists
    for user_id, user_data in users.items():
        if user_data.get("email") == email.lower():
            return {"success": False, "error": "Email already registered"}
    
    # Create new user
    user_id = secrets.token_urlsafe(16)
    users[user_id] = {
        "email": email.lower(),
        "password_hash": hash_password(password),
        "username": username or email.split("@")[0],
        "created_at": datetime.now().isoformat(),
        "x_username": None,
        "x_connected": False,
        "onboarding_complete": False,
        "onboarding_step": 1
    }
    
    save_users(users)
    
    return {
        "success": True,
        "user_id": user_id,
        "username": users[user_id]["username"]
    }


def login_user(email: str, password: str) -> Dict[str, Any]:
    """
    Login user and create session
    
    Returns:
        Dict with 'success', 'session_token', 'user_id' or 'error'
    """
    users = load_users()
    password_hash = hash_password(password)
    
    # Find user
    for user_id, user_data in users.items():
        if user_data.get("email") == email.lower() and user_data.get("password_hash") == password_hash:
            # Create session
            sessions = load_sessions()
            session_token = generate_session_token()
            sessions[session_token] = {
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "expires": (datetime.now() + timedelta(days=30)).isoformat()
            }
            save_sessions(sessions)
            
            return {
                "success": True,
                "session_token": session_token,
                "user_id": user_id,
                "username": user_data.get("username")
            }
    
    return {"success": False, "error": "Invalid email or password"}


def get_user_from_session(session_token: str) -> Optional[Dict[str, Any]]:
    """Get user data from session token"""
    sessions = load_sessions()
    session_data = sessions.get(session_token)
    
    if not session_data:
        return None
    
    # Check if expired
    expires = datetime.fromisoformat(session_data.get("expires", "2000-01-01"))
    if expires < datetime.now():
        return None
    
    users = load_users()
    user_id = session_data.get("user_id")
    user_data = users.get(user_id)
    
    if user_data:
        user_data["user_id"] = user_id
        return user_data
    
    return None


def update_user(user_id: str, updates: Dict[str, Any]) -> None:
    """Update user data"""
    users = load_users()
    if user_id in users:
        users[user_id].update(updates)
        save_users(users)


def get_user_data_dir(user_id: str) -> Path:
    """Get user-specific data directory"""
    user_dir = USERS_DIR / user_id
    user_dir.mkdir(exist_ok=True)
    return user_dir

