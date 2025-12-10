"""
Conversation State Manager
Manages conversation state, history, and context caching
In-memory storage for fast access (can be migrated to Redis later)
"""
from typing import Dict, List, Optional
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
    contact_id: Optional[str] = None
) -> Dict:
    """
    Create a new conversation state
    """
    state = {
        "call_sid": call_sid,
        "direction": direction,  # "inbound" or "outbound"
        "context": context,  # Full context from context_service
        "history": [],  # Conversation history for LLM
        "voice_agent_id": voice_agent_id,
        "real_estate_agent_id": real_estate_agent_id,
        "contact_id": contact_id,  # For outbound calls
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "turn_count": 0
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
