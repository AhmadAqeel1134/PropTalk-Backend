"""
Conversation State Manager
Manages conversation state, history, and context caching
In-memory storage for fast access (can be migrated to Redis later)
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# In-memory conversation state storage
# Structure: {call_sid: {context, history, direction, created_at, ...}}
_conversation_states: Dict[str, Dict] = {}

# TTL for conversation states (1 hour)
CONVERSATION_STATE_TTL = timedelta(hours=1)


def get_conversation_state(call_sid: str) -> Optional[Dict]:
    """
    Get conversation state for a call
    Returns None if state doesn't exist or has expired
    """
    if call_sid not in _conversation_states:
        return None
    
    state = _conversation_states[call_sid]
    
    # Check if state has expired
    created_at = state.get("created_at")
    if created_at and datetime.utcnow() - created_at > CONVERSATION_STATE_TTL:
        logger.info(f"🗑️ Conversation state expired for call {call_sid}")
        del _conversation_states[call_sid]
        return None
    
    return state


def create_conversation_state(
    call_sid: str,
    direction: str,
    context: Dict,
    voice_agent_id: str,
    real_estate_agent_id: str,
    contact_id: Optional[str] = None,
    caller_phone: Optional[str] = None,
) -> Dict:
    """
    Create a new conversation state
    """
    # Pre-fill caller info from context if the caller is a known contact
    known_name = None
    known_email = None
    caller_contact = context.get("caller_contact") if context else None
    if caller_contact:
        if caller_contact.get("name"):
            known_name = caller_contact["name"]
        if caller_contact.get("email"):
            known_email = caller_contact["email"]

    state = {
        "call_sid": call_sid,
        "direction": direction,  # "inbound" or "outbound"
        "context": context,  # Full context from context_service
        "history": [],  # Conversation history for LLM
        "voice_agent_id": voice_agent_id,
        "real_estate_agent_id": real_estate_agent_id,
        "contact_id": contact_id or (caller_contact.get("id") if caller_contact else None),
        "caller_phone": caller_phone,
        "caller_name": known_name,
        "caller_email": known_email,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "turn_count": 0,
        # Booking / intent tracking
        "active_intent": None,  # e.g. "schedule_showing"
        "slots": {},            # collected booking fields
        "pending_confirmation": False,
        # Topic tracking — prevents the agent from repeating confirmed topics
        "confirmed_topics": set(),
    }
    
    _conversation_states[call_sid] = state
    logger.info(f"✅ Created conversation state for call {call_sid} ({direction})")
    return state


def update_conversation_history(
    call_sid: str,
    role: str,  # "system", "user", or "assistant"
    content: str
) -> bool:
    """
    Add a message to conversation history
    Returns True if successful, False if state doesn't exist
    """
    state = get_conversation_state(call_sid)
    if not state:
        logger.warning(f"⚠️ Cannot update history - state not found for call {call_sid}")
        return False
    
    # Add to history
    state["history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Update metadata
    state["updated_at"] = datetime.utcnow()
    state["turn_count"] = len([h for h in state["history"] if h["role"] == "user"])
    
    logger.debug(f"📝 Updated history for call {call_sid} - Turn {state['turn_count']}")
    return True


def get_conversation_history(call_sid: str) -> List[Dict]:
    """
    Get conversation history for a call
    Returns empty list if state doesn't exist
    """
    state = get_conversation_state(call_sid)
    if not state:
        return []
    
    return state.get("history", [])


def get_cached_context(call_sid: str) -> Optional[Dict]:
    """
    Get cached context for a call
    Returns None if state doesn't exist
    """
    state = get_conversation_state(call_sid)
    if not state:
        return None
    
    return state.get("context")


def clear_conversation_state(call_sid: str) -> bool:
    """
    Clear conversation state for a call (when call ends)
    Returns True if state was cleared, False if it didn't exist
    """
    if call_sid in _conversation_states:
        del _conversation_states[call_sid]
        logger.info(f"🗑️ Cleared conversation state for call {call_sid}")
        return True
    return False


def cleanup_expired_states() -> int:
    """
    Clean up expired conversation states
    Returns number of states cleaned up
    """
    now = datetime.utcnow()
    expired_sids = []
    
    for call_sid, state in _conversation_states.items():
        created_at = state.get("created_at")
        if created_at and now - created_at > CONVERSATION_STATE_TTL:
            expired_sids.append(call_sid)
    
    for call_sid in expired_sids:
        del _conversation_states[call_sid]
    
    if expired_sids:
        logger.info(f"🧹 Cleaned up {len(expired_sids)} expired conversation states")
    
    return len(expired_sids)


def get_state_stats() -> Dict:
    """
    Get statistics about conversation states (for monitoring)
    """
    return {
        "total_states": len(_conversation_states),
        "states": {
            "inbound": len([s for s in _conversation_states.values() if s.get("direction") == "inbound"]),
            "outbound": len([s for s in _conversation_states.values() if s.get("direction") == "outbound"])
        }
    }


# --------------- intent / slot helpers ---------------

def set_active_intent(call_sid: str, intent: str) -> bool:
    """Set the active intent for the call (e.g. 'schedule_showing')."""
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["active_intent"] = intent
    state["slots"] = {}
    state["pending_confirmation"] = False
    logger.debug(f"🎯 Set intent={intent} for call {call_sid}")
    return True


def get_active_intent(call_sid: str) -> Optional[str]:
    state = get_conversation_state(call_sid)
    return state.get("active_intent") if state else None


def update_slots(call_sid: str, new_slots: Dict) -> bool:
    """Merge new slot values into the existing slots dict."""
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["slots"].update(new_slots)
    state["updated_at"] = datetime.utcnow()
    logger.debug(f"📝 Slots updated for call {call_sid}: {list(new_slots.keys())}")
    return True


def get_slots(call_sid: str) -> Dict:
    state = get_conversation_state(call_sid)
    return state.get("slots", {}) if state else {}


def set_pending_confirmation(call_sid: str, pending: bool) -> bool:
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["pending_confirmation"] = pending
    return True


def is_pending_confirmation(call_sid: str) -> bool:
    state = get_conversation_state(call_sid)
    return state.get("pending_confirmation", False) if state else False


def clear_intent(call_sid: str) -> bool:
    """Reset intent tracking after completion or cancellation."""
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["active_intent"] = None
    state["slots"] = {}
    state["pending_confirmation"] = False
    return True


# --------------- personalization helpers ---------------

def set_caller_name(call_sid: str, name: str) -> bool:
    """Store the caller's name for personalised responses throughout the call."""
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["caller_name"] = name
    if state.get("slots") is not None:
        state["slots"]["caller_name"] = name
    return True


def get_caller_name(call_sid: str) -> Optional[str]:
    state = get_conversation_state(call_sid)
    if not state:
        return None
    return state.get("caller_name") or (state.get("slots") or {}).get("caller_name")


def set_caller_email(call_sid: str, email: str) -> bool:
    """Store the caller's email so notifications work end-to-end."""
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["caller_email"] = email
    if state.get("slots") is not None:
        state["slots"]["caller_email"] = email
    return True


def get_caller_email(call_sid: str) -> Optional[str]:
    state = get_conversation_state(call_sid)
    if not state:
        return None
    return state.get("caller_email") or (state.get("slots") or {}).get("caller_email")


def set_last_discussed_property(call_sid: str, property_info: Dict) -> bool:
    """Track the most-recently discussed property so 'that one' / 'tell me more' can resolve."""
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["last_discussed_property"] = property_info
    return True


def get_last_discussed_property(call_sid: str) -> Optional[Dict]:
    state = get_conversation_state(call_sid)
    return state.get("last_discussed_property") if state else None


# --------------- topic tracking helpers ---------------

def mark_topic_confirmed(call_sid: str, topic: str) -> bool:
    """Mark a conversation topic as confirmed so the agent does not repeat it."""
    state = get_conversation_state(call_sid)
    if not state:
        return False
    state["confirmed_topics"].add(topic)
    logger.debug(f"✅ Topic confirmed for call {call_sid}: {topic}")
    return True


def get_confirmed_topics(call_sid: str) -> Set[str]:
    state = get_conversation_state(call_sid)
    return state.get("confirmed_topics", set()) if state else set()


def get_turn_count(call_sid: str) -> int:
    """Return the number of user turns so far (useful for early-call logic)."""
    state = get_conversation_state(call_sid)
    return state.get("turn_count", 0) if state else 0
