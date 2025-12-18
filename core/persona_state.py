"""Persona State Manager - Core brain of the system"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import config

# Default Persona State structure
DEFAULT_PERSONA_STATE = {
    "topic_affinity": {
        "saas": 0.5,
        "ai": 0.5,
        "startups": 0.5,
        "product": 0.5,
        "distribution": 0.5,
        "operations": 0.5,
        "online_business": 0.5,
        "money": 0.5,
        "personal_reflections": 0.5,
        "humor": 0.5
    },
    "tone_style": {
        "sentence_length": "medium",
        "question_frequency": 0.4,
        "humor_frequency": 0.2,
        "emotional_intensity": "moderate",
        "formality": "casual",
        "contrarian_tolerance": 0.5,
        "certainty_level": "balanced"
    },
    "engagement_behavior": {
        "likes_per_day_baseline": 20,
        "replies_per_day_baseline": 5,
        "follow_after_reply_tendency": 0.3,
        "early_engagement_tendency": 0.7,
        "reply_depth_preference": "medium"
    },
    "risk_sensitivity": {
        "hot_takes_comfort": 0.4,
        "safe_vs_experimental": 0.6,
        "challenge_others_tendency": 0.5
    },
    "energy_cadence": {
        "posts_per_day_tolerance": 2,
        "engagement_fatigue_signals": [],
        "preferred_posting_times": ["09:00", "17:00"],
        "consistency_preference": "moderate"
    },
    "learning_history": {
        "total_approvals": 0,
        "total_rejections": 0,
        "total_edits": 0,
        "last_updated": None
    }
}


def load_persona_state() -> Dict[str, Any]:
    """Load Persona State from JSON file, create default if doesn't exist"""
    if config.PERSONA_STATE_FILE.exists():
        try:
            with open(config.PERSONA_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                # Merge with defaults to ensure all keys exist
                return _merge_with_defaults(state)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading persona state: {e}. Using defaults.")
            return _create_default_state()
    else:
        return _create_default_state()


def _merge_with_defaults(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge loaded state with defaults to ensure all keys exist"""
    merged = DEFAULT_PERSONA_STATE.copy()
    
    for key, value in state.items():
        if isinstance(value, dict) and key in merged:
            merged[key].update(value)
        else:
            merged[key] = value
    
    return merged


def _create_default_state() -> Dict[str, Any]:
    """Create and save default Persona State"""
    state = json.loads(json.dumps(DEFAULT_PERSONA_STATE))  # Deep copy
    save_persona_state(state)
    return state


def save_persona_state(state: Dict[str, Any]) -> None:
    """Save Persona State to JSON file"""
    # Validate state structure
    state = _validate_state(state)
    
    # Update last_updated timestamp
    if "learning_history" in state:
        state["learning_history"]["last_updated"] = datetime.now().isoformat()
    
    with open(config.PERSONA_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _validate_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize Persona State values"""
    validated = {}
    
    # Validate topic_affinity (0-1 range)
    if "topic_affinity" in state:
        validated["topic_affinity"] = {}
        for topic, value in state["topic_affinity"].items():
            validated["topic_affinity"][topic] = max(0.0, min(1.0, float(value)))
    
    # Validate tone_style
    if "tone_style" in state:
        validated["tone_style"] = state["tone_style"].copy()
        # Ensure numeric values are in 0-1 range
        for key, value in validated["tone_style"].items():
            if isinstance(value, (int, float)):
                validated["tone_style"][key] = max(0.0, min(1.0, float(value)))
    
    # Validate engagement_behavior
    if "engagement_behavior" in state:
        validated["engagement_behavior"] = state["engagement_behavior"].copy()
        for key, value in validated["engagement_behavior"].items():
            if isinstance(value, (int, float)):
                if "baseline" in key or "tendency" in key:
                    validated["engagement_behavior"][key] = max(0.0, min(1.0, float(value)))
    
    # Validate risk_sensitivity (0-1 range)
    if "risk_sensitivity" in state:
        validated["risk_sensitivity"] = {}
        for key, value in state["risk_sensitivity"].items():
            validated["risk_sensitivity"][key] = max(0.0, min(1.0, float(value)))
    
    # Validate energy_cadence
    if "energy_cadence" in state:
        validated["energy_cadence"] = state["energy_cadence"].copy()
    
    # Preserve learning_history
    if "learning_history" in state:
        validated["learning_history"] = state["learning_history"]
    
    return validated


def update_from_feedback(feedback_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update Persona State from feedback (incremental updates only)"""
    state = load_persona_state()
    changes = []
    
    # Maximum change per update (0.1 = 10%)
    MAX_CHANGE = 0.1
    
    if feedback_type == "topic_affinity":
        if "topic" in data and "adjustment" in data:
            topic = data["topic"]
            adjustment = float(data["adjustment"])
            # Clamp adjustment
            adjustment = max(-MAX_CHANGE, min(MAX_CHANGE, adjustment))
            
            if topic in state["topic_affinity"]:
                old_value = state["topic_affinity"][topic]
                new_value = max(0.0, min(1.0, old_value + adjustment))
                state["topic_affinity"][topic] = new_value
                changes.append(f"Topic '{topic}': {old_value:.2f} → {new_value:.2f}")
    
    elif feedback_type == "tone_style":
        if "attribute" in data and "adjustment" in data:
            attr = data["attribute"]
            adjustment = float(data["adjustment"])
            adjustment = max(-MAX_CHANGE, min(MAX_CHANGE, adjustment))
            
            if attr in state["tone_style"]:
                if isinstance(state["tone_style"][attr], (int, float)):
                    old_value = state["tone_style"][attr]
                    new_value = max(0.0, min(1.0, old_value + adjustment))
                    state["tone_style"][attr] = new_value
                    changes.append(f"Tone '{attr}': {old_value:.2f} → {new_value:.2f}")
    
    elif feedback_type == "engagement_behavior":
        if "attribute" in data and "adjustment" in data:
            attr = data["attribute"]
            adjustment = float(data["adjustment"])
            
            if attr in state["engagement_behavior"]:
                if isinstance(state["engagement_behavior"][attr], (int, float)):
                    if "baseline" in attr:
                        # For baselines, allow larger changes
                        old_value = state["engagement_behavior"][attr]
                        new_value = max(0, old_value + int(adjustment))
                        state["engagement_behavior"][attr] = new_value
                        changes.append(f"Engagement '{attr}': {old_value} → {new_value}")
                    else:
                        # For tendencies, use MAX_CHANGE
                        adjustment = max(-MAX_CHANGE, min(MAX_CHANGE, adjustment))
                        old_value = state["engagement_behavior"][attr]
                        new_value = max(0.0, min(1.0, old_value + adjustment))
                        state["engagement_behavior"][attr] = new_value
                        changes.append(f"Engagement '{attr}': {old_value:.2f} → {new_value:.2f}")
    
    elif feedback_type == "risk_sensitivity":
        if "attribute" in data and "adjustment" in data:
            attr = data["attribute"]
            adjustment = float(data["adjustment"])
            adjustment = max(-MAX_CHANGE, min(MAX_CHANGE, adjustment))
            
            if attr in state["risk_sensitivity"]:
                old_value = state["risk_sensitivity"][attr]
                new_value = max(0.0, min(1.0, old_value + adjustment))
                state["risk_sensitivity"][attr] = new_value
                changes.append(f"Risk '{attr}': {old_value:.2f} → {new_value:.2f}")
    
    elif feedback_type == "energy_cadence":
        if "attribute" in data:
            attr = data["attribute"]
            if attr == "posts_per_day_tolerance" and "value" in data:
                # Allow direct updates for tolerance
                state["energy_cadence"][attr] = max(0, int(data["value"]))
                changes.append(f"Energy '{attr}': → {state['energy_cadence'][attr]}")
            elif attr == "fatigue_signal" and "signal" in data:
                # Add fatigue signal
                if "engagement_fatigue_signals" not in state["energy_cadence"]:
                    state["energy_cadence"]["engagement_fatigue_signals"] = []
                state["energy_cadence"]["engagement_fatigue_signals"].append({
                    "timestamp": datetime.now().isoformat(),
                    "signal": data["signal"]
                })
                # Keep only last 7 days of signals
                state["energy_cadence"]["engagement_fatigue_signals"] = state["energy_cadence"]["engagement_fatigue_signals"][-30:]
    
    # Update learning history
    if "action" in data:
        action = data["action"]
        if action == "approval":
            state["learning_history"]["total_approvals"] += 1
        elif action == "rejection":
            state["learning_history"]["total_rejections"] += 1
        elif action == "edit":
            state["learning_history"]["total_edits"] += 1
    
    save_persona_state(state)
    
    return {
        "state": state,
        "changes": changes,
        "explanation": "; ".join(changes) if changes else "No changes made"
    }


def get_persona_explanation() -> str:
    """Generate human-readable explanation of current Persona State"""
    state = load_persona_state()
    
    lines = []
    lines.append("=== PERSONA STATE SUMMARY ===\n")
    
    # Topic Affinity
    lines.append("TOPIC AFFINITY:")
    top_topics = sorted(
        state["topic_affinity"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    for topic, weight in top_topics:
        lines.append(f"  • {topic}: {weight:.1%}")
    
    # Tone & Style
    lines.append("\nTONE & STYLE:")
    tone = state["tone_style"]
    lines.append(f"  • Sentence length: {tone['sentence_length']}")
    lines.append(f"  • Question frequency: {tone['question_frequency']:.1%}")
    lines.append(f"  • Humor frequency: {tone['humor_frequency']:.1%}")
    lines.append(f"  • Formality: {tone['formality']}")
    lines.append(f"  • Contrarian tolerance: {tone['contrarian_tolerance']:.1%}")
    
    # Engagement Behavior
    lines.append("\nENGAGEMENT BEHAVIOR:")
    eng = state["engagement_behavior"]
    lines.append(f"  • Likes per day: {eng['likes_per_day_baseline']}")
    lines.append(f"  • Replies per day: {eng['replies_per_day_baseline']}")
    lines.append(f"  • Early engagement tendency: {eng['early_engagement_tendency']:.1%}")
    
    # Risk Sensitivity
    lines.append("\nRISK SENSITIVITY:")
    risk = state["risk_sensitivity"]
    lines.append(f"  • Hot takes comfort: {risk['hot_takes_comfort']:.1%}")
    lines.append(f"  • Safe vs experimental: {risk['safe_vs_experimental']:.1%}")
    
    # Energy & Cadence
    lines.append("\nENERGY & CADENCE:")
    energy = state["energy_cadence"]
    lines.append(f"  • Posts per day tolerance: {energy['posts_per_day_tolerance']}")
    lines.append(f"  • Preferred posting times: {', '.join(energy['preferred_posting_times'])}")
    
    # Learning History
    lines.append("\nLEARNING HISTORY:")
    hist = state["learning_history"]
    lines.append(f"  • Total approvals: {hist['total_approvals']}")
    lines.append(f"  • Total rejections: {hist['total_rejections']}")
    lines.append(f"  • Total edits: {hist['total_edits']}")
    if hist.get("last_updated"):
        lines.append(f"  • Last updated: {hist['last_updated']}")
    
    return "\n".join(lines)

