"""
Twilio Webhook Service - Handle Twilio webhooks and voice flow
STT → LLM → TTS pipeline
Orchestrates AI services for intelligent voice conversations

PERFORMANCE OPTIMIZATIONS:
- Returns TwiML within 1 second (Twilio requirement: < 3s)
- Database queries minimized and optimized
- Background tasks for non-critical operations
- Caching for frequently accessed data
"""
from typing import Dict, Optional
import httpx
import uuid
import asyncio
import logging
from datetime import datetime
from twilio.twiml.voice_response import VoiceResponse, Gather
from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.models.voice_agent import VoiceAgent
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from functools import lru_cache

# Import new modular services
from app.services.conversation.state_manager import (
    get_conversation_state,
    create_conversation_state,
    update_conversation_history,
    get_conversation_history,
    clear_conversation_state
)
from app.services.ai.context_service import (
    build_outbound_context,
    build_inbound_context
)
from app.services.ai.prompt_service import (
    build_outbound_prompt,
    build_inbound_prompt,
    get_initial_greeting_prompt
)
from app.services.ai.llm_service import (
    process_with_llm,
    generate_initial_greeting
)
from app.services.call_service import save_transcript_by_twilio_sid

logger = logging.getLogger(__name__)

# Simple in-memory cache for phone number lookups (cleared every 5 minutes)
_phone_cache = {}
_cache_timestamp = datetime.utcnow()


def _should_end_call(user_input: str, llm_response: str, conversation_state: Optional[Dict], is_outbound: bool) -> bool:
    """
    Determine if the call should be ended based on user input or LLM response.
    Returns True if call should end, False otherwise.
    """
    user_lower = user_input.lower()
    llm_lower = llm_response.lower()
    
    # Check if user says they're not the right person (outbound only)
    if is_outbound:
        # Patterns indicating wrong person
        # Check for simple "no" first (most common response to verification question)
        if user_lower.strip() == "no" or user_lower.strip() == "no.":
            logger.info(f"🛑 User said 'no' to verification question: '{user_input}'")
            return True
        
        wrong_person_patterns = [
            "no i'm not",
            "no i am not",
            "i'm not",
            "i am not",
            "wrong person",
            "wrong number",
            "you have the wrong",
            "that's not me",
            "that's not my name",
            "no, that's not",
            "no that's not",
            "no it's not",
            "no it is not",
            "this is not",
            "this isn't"
        ]
        for pattern in wrong_person_patterns:
            if pattern in user_lower:
                logger.info(f"🛑 User indicated wrong person: '{user_input}'")
                return True
        
        # Check for "not interested" patterns (different from wrong person)
        not_interested_patterns = [
            "not interested",
            "not intrested",  # typo
            "no interest",
            "don't want to sell",
            "dont want to sell",
            "not selling",
            "not going to sell",
            "wont sell",
            "won't sell",
            "not looking to sell"
        ]
        for pattern in not_interested_patterns:
            if pattern in user_lower:
                logger.info(f"🛑 User indicated not interested: '{user_input}'")
                return True  # End call but with different message (handled by LLM)
    
    # Check if user says no questions / ready to end (works for both inbound and outbound)
    no_questions_patterns = [
        "no questions",
        "no question",
        "no, that's all",
        "no that's all",
        "no i'm good",
        "no im good",
        "no, i'm done",
        "no im done",
        "that's all",
        "thats all",
        "no more questions",
        "no other questions",
        "nothing else",
        "no nothing",
        "no, nothing",
        "no thanks",
        "no thank you",
        "i'm all set",
        "im all set",
        "i'll call back",
        "ill call back",
        "i'll call later",
        "ill call later",
        "not interested",
        "not right now"
    ]
    for pattern in no_questions_patterns:
        if pattern in user_lower:
            logger.info(f"🛑 User indicated no more questions: '{user_input}'")
            return True
    
    # Check if LLM response indicates ending (apology + goodbye)
    ending_phrases = [
        "sorry for the inconvenience",
        "apologize for the inconvenience",
        "have a good day",
        "have a great day",
        "goodbye",
        "good bye",
        "sorry to bother you"
    ]
    ending_count = sum(1 for phrase in ending_phrases if phrase in llm_lower)
    if ending_count >= 2:  # At least 2 ending phrases (e.g., "sorry" + "goodbye")
        logger.info(f"🛑 LLM response indicates call should end: '{llm_response[:50]}...'")
        return True
    
    return False


def _generate_natural_fallback(user_input: str, conversation_state: Optional[Dict], is_outbound: bool) -> str:
    """
    Generate natural, conversational fallback responses without always repeating what was said.
    Uses varied responses that feel more human-like.
    """
    user_lower = user_input.lower()
    turn_count = conversation_state.get("turn_count", 0) if conversation_state else 0
    
    # Responses for "can you hear me" type questions
    if "hear" in user_lower or "can you" in user_lower:
        responses = [
            "Yes, I can hear you perfectly! How can I help you today?",
            "Absolutely, I can hear you clearly. What can I do for you?",
            "Yes, I'm listening. How may I assist you?",
            "I can hear you just fine. What would you like to know?",
        ]
        return responses[turn_count % len(responses)]
    
    # Greetings
    if "hello" in user_lower or "hi" in user_lower or "hey" in user_lower:
        responses = [
            "Hello! How can I help you today?",
            "Hi there! What can I do for you?",
            "Hello! I'm here to assist you. What would you like to know?",
        ]
        return responses[turn_count % len(responses)]
    
    # Property-related queries
    if "property" in user_lower or "sell" in user_lower or "buy" in user_lower or "house" in user_lower or "apartment" in user_lower or "condo" in user_lower:
        if is_outbound:
            responses = [
                "I'd be happy to help you with your property. What would you like to know?",
                "Let me help you with that. What questions do you have about your property?",
                "I can assist you with property information. What are you interested in?",
            ]
        else:
            responses = [
                "I can help you find properties. What are you looking for?",
                "Let me help you with property information. What type of property interests you?",
                "I'd be happy to assist you. What kind of property are you searching for?",
                "I can help you find the perfect property. What are your requirements?",
            ]
        return responses[turn_count % len(responses)]
    
    # Inbound-specific: Price, location, bedroom queries
    if not is_outbound and ("price" in user_lower or "cost" in user_lower or "bedroom" in user_lower or "bathroom" in user_lower or "location" in user_lower or "city" in user_lower):
        responses = [
            "I can help you find properties based on your criteria. What are you looking for?",
            "Let me help you with that. What type of property and price range are you interested in?",
            "I'd be happy to assist you. What are your requirements for the property?",
        ]
        return responses[turn_count % len(responses)]
    
    # Questions about identity/who they are
    if "who" in user_lower and ("i" in user_lower or "you" in user_lower or "am" in user_lower):
        if is_outbound:
            responses = [
                "I'm calling about your property. How can I help you today?",
                "I'm here to discuss your property. What would you like to know?",
                "I'm reaching out regarding your property. How may I assist you?",
            ]
        else:
            responses = [
                "I'm here to help you find properties. What are you looking for?",
                "I can assist you with property information. What do you need?",
            ]
        return responses[turn_count % len(responses)]
    
    # Communication/understanding questions
    if "understand" in user_lower or "communicat" in user_lower or "talk" in user_lower:
        responses = [
            "I understand you. How can I help you?",
            "I'm here and listening. What can I do for you?",
            "Yes, I'm following along. What would you like to know?",
        ]
        return responses[turn_count % len(responses)]
    
    # Ending calls
    if "end" in user_lower or "bye" in user_lower or "goodbye" in user_lower or "hang up" in user_lower:
        responses = [
            "Thank you for your time. Have a great day!",
            "Thanks for calling. Take care!",
            "I appreciate your time. Goodbye!",
        ]
        return responses[turn_count % len(responses)]
    
    # Default natural responses (don't repeat what was said)
    default_responses = [
        "I understand. How can I help you with that?",
        "Got it. What would you like to know?",
        "I see. Let me help you with that.",
        "Sure. What can I do for you?",
        "Okay. How may I assist you?",
        "I'm here to help. What do you need?",
    ]
    
    # Use turn count to vary responses
    return default_responses[turn_count % len(default_responses)]

def _get_cached_phone_data(phone_number: str) -> Optional[Dict]:
    """Get cached phone/agent data if available and fresh"""
    global _cache_timestamp
    # Clear cache if older than 5 minutes
    if (datetime.utcnow() - _cache_timestamp).total_seconds() > 300:
        _phone_cache.clear()
        _cache_timestamp = datetime.utcnow()
        return None
    return _phone_cache.get(phone_number)

def _cache_phone_data(phone_number: str, data: Dict):
    """Cache phone/agent data"""
    _phone_cache[phone_number] = data


async def handle_voice_webhook(form_data: Dict) -> str:
    """
    Handle incoming voice webhook from Twilio
    Returns TwiML XML response
    
    CRITICAL PERFORMANCE REQUIREMENTS:
    - MUST respond within 3 seconds (Twilio timeout)
    - Target: < 1 second for best experience
    - Strategy: Return TwiML immediately, process everything else in background
    """
    try:
        start_time = datetime.utcnow()
        
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        call_sid = form_data.get("CallSid", "")
        speech_result = form_data.get("SpeechResult", "")
        direction = form_data.get("Direction", "")
        
        logger.info(f"📞 Webhook received - Direction: {direction}, From: {from_number}, To: {to_number}, SID: {call_sid}")
        logger.info(f"📋 Full form_data keys: {list(form_data.keys())}")
        print(f"\n{'='*60}")
        print(f"📥 WEBHOOK RECEIVED")
        print(f"   Call SID: {call_sid}")
        print(f"   From: {from_number}")
        print(f"   To: {to_number}")
        print(f"   Direction: {direction}")
        print(f"   Speech Result: {speech_result[:50] if speech_result else 'None'}")
        print(f"{'='*60}\n")
        
        # Determine which number to look up based on call direction
        is_outbound = direction.startswith("outbound")
        twilio_number = from_number if is_outbound else to_number
        
        logger.info(f"📞 {direction} call - From: {from_number}, To: {to_number}, SID: {call_sid}")
        logger.info(f"🔍 Looking up voice agent for Twilio number: {twilio_number} (is_outbound: {is_outbound})")
        
        # ============================================================
        # PHASE 1: MINIMAL DATABASE LOOKUP (Target: < 500ms)
        # ============================================================
        
        # Initialize variables (will be set by lookup or cache)
        voice_agent_id = None
        voice_agent_name = None
        real_estate_agent_id = None
        
        # Try cache first
        cached_data = _get_cached_phone_data(twilio_number)
        
        if cached_data:
            logger.info(f"⚡ Using cached data for {twilio_number}")
            voice_agent_id = cached_data.get("voice_agent_id")
            voice_agent_name = cached_data.get("voice_agent_name")
            real_estate_agent_id = cached_data.get("real_estate_agent_id")
        else:
            # Database lookup - single optimized query
            try:
                async with AsyncSessionLocal() as session:
                    # Normalize phone number
                    normalized_number = twilio_number.strip().replace(" ", "").replace("-", "")
                    if not normalized_number.startswith("+"):
                        normalized_number = "+" + normalized_number
                    
                    # SINGLE OPTIMIZED QUERY: Get phone + agent in one go
                    from sqlalchemy.orm import aliased
                    va_alias = aliased(VoiceAgent)
                    stmt = (
                        select(PhoneNumber.id, PhoneNumber.is_active, 
                               va_alias.id, va_alias.name, va_alias.status, va_alias.real_estate_agent_id)
                        .outerjoin(va_alias, PhoneNumber.id == va_alias.phone_number_id)
                        .where(PhoneNumber.twilio_phone_number == normalized_number)
                    )
                    result = await session.execute(stmt)
                    row = result.first()
                    
                    logger.info(f"🔍 Database lookup result for '{normalized_number}': {row}")
                
                    if not row or not row[2]:  # No phone or no agent
                        logger.error(f"❌ Phone/Agent not found for {twilio_number} (normalized: {normalized_number})")
                        # Try to find what numbers exist in DB for debugging
                        debug_stmt = select(PhoneNumber.twilio_phone_number).limit(5)
                        debug_result = await session.execute(debug_stmt)
                        debug_numbers = [r[0] for r in debug_result.all()]
                        logger.error(f"🔍 Sample phone numbers in DB: {debug_numbers}")
                        return _generate_error_twiml("The voice agent is not available.")
                    
                    phone_id, is_active, agent_id, agent_name, agent_status, re_agent_id = row
                    
                    logger.info(f"✅ Found phone_id={phone_id}, is_active={is_active}, agent_id={agent_id}, agent_name={agent_name}, agent_status={agent_status}")
                    
                    if not is_active or agent_status != "active":
                        logger.warning(f"❌ Phone/Agent inactive for {twilio_number}: is_active={is_active}, agent_status={agent_status}")
                        return _generate_error_twiml("The voice agent is not available.")
                    
                    # Cache for next time
                    voice_agent_id = agent_id
                    voice_agent_name = agent_name
                    real_estate_agent_id = re_agent_id
                    
                    _cache_phone_data(twilio_number, {
                        "voice_agent_id": agent_id,
                        "voice_agent_name": agent_name,
                        "real_estate_agent_id": re_agent_id
                    })
                    
                    logger.info(f"✅ Found agent: {agent_name} (ID: {agent_id})")
                    
            except Exception as db_error:
                logger.error(f"❌ DB error in webhook handler: {db_error}", exc_info=True)
                import traceback
                logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                # Don't return error here - let it fall through to use fallback values
                # voice_agent_name will be None, which we'll handle below
        
        # Validate that we have required data
        if not voice_agent_id or not voice_agent_name:
            logger.error(f"❌ Missing voice agent data - voice_agent_id: {voice_agent_id}, voice_agent_name: {voice_agent_name}")
            print(f"\n❌ MISSING VOICE AGENT DATA:")
            print(f"   voice_agent_id: {voice_agent_id}")
            print(f"   voice_agent_name: {voice_agent_name}")
            print(f"   real_estate_agent_id: {real_estate_agent_id}\n")
            return _generate_error_twiml("The voice agent is not available.")
        
        # ============================================================
        # PHASE 2: GENERATE TWIML IMMEDIATELY (No more DB queries!)
        # ============================================================
        
        response = VoiceResponse()
        webhook_base_url = settings.TWILIO_VOICE_WEBHOOK_URL or ""
        voice_webhook_url = f"{webhook_base_url}/webhooks/twilio/voice" if webhook_base_url else "/webhooks/twilio/voice"
        
        # Check if user spoke (continuation) or initial call
        is_continuation = bool(speech_result and speech_result.strip())
        
        if is_continuation:
            # ============================================================
            # USER SPOKE - Process with LLM
            # ============================================================
            logger.info(f"💬 User spoke: '{speech_result}' (full text captured by Twilio STT)")
            print(f"\n{'='*60}")
            print(f"🎤 USER SPEECH CAPTURED BY TWILIO STT:")
            print(f"   Text: '{speech_result}'")
            print(f"   Call SID: {call_sid}")
            print(f"{'='*60}\n")
            
            # Get conversation state (in-memory, fast)
            conversation_state = get_conversation_state(call_sid)
            
            if not conversation_state:
                # First user response - create state quickly
                conversation_state = create_conversation_state(
                    call_sid=call_sid,
                    direction="outbound" if is_outbound else "inbound",
                    context={},
                    voice_agent_id=voice_agent_id,
                    real_estate_agent_id=real_estate_agent_id,
                    contact_id=None
                )
            
            # Add user message
            update_conversation_history(call_sid, "user", speech_result)
            history = get_conversation_history(call_sid)
            
            # Get context (may be empty if still building in background)
            context = conversation_state.get("context", {})
            
            # Build system prompt
            if context and not context.get("error"):
                if is_outbound:
                    from app.services.ai.prompt_service import build_outbound_prompt
                    system_prompt = build_outbound_prompt(context)
                else:
                    from app.services.ai.prompt_service import build_inbound_prompt
                    system_prompt = build_inbound_prompt(context)
            else:
                # Fallback prompt
                system_prompt = f"You are {voice_agent_name}, a helpful real estate assistant. Be professional and concise."
            
            # Get LLM response with timeout (using Gemini)
            try:
                llm_response = await asyncio.wait_for(
                    process_with_llm(
                        user_input=speech_result,
                        system_prompt=system_prompt,
                        conversation_history=history,
                        max_tokens=150,  # Gemini allows more tokens
                        timeout=4.0  # Slightly longer for Gemini
                    ),
                    timeout=3.5  # Overall timeout
                )
                
                update_conversation_history(call_sid, "assistant", llm_response)
                response.say(llm_response, voice="alice")
                logger.info(f"✅ LLM: {llm_response[:50]}...")
                
                # Check if we should end the call (wrong person, no questions, or LLM indicates ending)
                if _should_end_call(speech_result, llm_response, conversation_state, is_outbound):
                    logger.info(f"🛑 Ending call based on user input or LLM response")
                    response.hangup()
                    return str(response)
                
            except asyncio.TimeoutError:
                logger.warning("⏱️ LLM timeout, using natural fallback")
                fallback = _generate_natural_fallback(speech_result, conversation_state, is_outbound)
                response.say(fallback, voice="alice")
                update_conversation_history(call_sid, "assistant", fallback)
                
                # Check if we should end the call even with fallback
                if _should_end_call(speech_result, fallback, conversation_state, is_outbound):
                    logger.info(f"🛑 Ending call based on user input (timeout fallback)")
                    response.hangup()
                    return str(response)
                
            except Exception as llm_error:
                logger.error(f"❌ LLM error: {llm_error}")
                error_str = str(llm_error).lower()
                
                # Check if we've already mentioned technical issues
                fallback_mentioned = conversation_state.get("fallback_mentioned", False) if conversation_state else False
                
                # Handle API quota/rate limit errors (Gemini or other)
                if "quota" in error_str or "429" in error_str or "insufficient_quota" in error_str or "rate limit" in error_str:
                    logger.error("⚠️ API quota/rate limit exceeded - using natural fallback")
                    # Only mention technical issue once
                    if not fallback_mentioned:
                        if conversation_state:
                            conversation_state["fallback_mentioned"] = True
                        fallback = "I'm having some technical difficulties right now, but I can still hear you. Let me try to help you with what I can."
                    else:
                        # Already mentioned - use natural responses
                        fallback = _generate_natural_fallback(speech_result, conversation_state, is_outbound)
                else:
                    # Generic error - use natural fallback (but log for debugging)
                    logger.warning(f"⚠️ LLM error (non-quota): {error_str[:100]}")
                    fallback = _generate_natural_fallback(speech_result, conversation_state, is_outbound)
                
                response.say(fallback, voice="alice")
                update_conversation_history(call_sid, "assistant", fallback)
                
                # Check if we should end the call even with fallback
                if _should_end_call(speech_result, fallback, conversation_state, is_outbound):
                    logger.info(f"🛑 Ending call based on user input (error fallback)")
                    response.hangup()
                    return str(response)
                
        else:
            # ============================================================
            # NO SPEECH CAPTURED
            # If we've already greeted (conversation state exists), don't repeat intro;
            # instead, send a quick check-in to handle brief silence.
            # ============================================================
            existing_state = get_conversation_state(call_sid)
            if existing_state:
                context = existing_state.get("context", {}) or {}
                contact_name = ""
                try:
                    contact_ctx = context.get("contact") or {}
                    if isinstance(contact_ctx, dict):
                        contact_name = contact_ctx.get("name") or ""
                except Exception:
                    contact_name = ""
                check_in = (
                    f"Hello, are you there? This is {voice_agent_name}"
                    f"{f', calling for {contact_name}' if contact_name else ''}."
                )
                response.say(check_in, voice="alice")
                logger.info(f"🔁 Silence detected, sending check-in instead of repeating greeting: '{check_in}'")
            else:
                # ============================================================
                # INITIAL CALL - Proper greeting following prompt structure
                # ============================================================
                logger.info(f"👋 Initial call greeting")
                
                # voice_agent_name should be set by now from database lookup
                if not voice_agent_name:
                    logger.error("❌ voice_agent_name is None in initial greeting!")
                    return _generate_error_twiml("The voice agent is not available.")
                
                if is_outbound:
                    # For outbound: Quick lookup for contact name and agent info
                    # Strategy: Try Contact table first, then Property.owner_phone as fallback
                    contact_name = None
                    agent_name = None
                    company_name = None
                    property_address = None
                    contact_phone = None
                    
                    # Try quick lookup (with timeout to avoid blocking)
                    try:
                        async with AsyncSessionLocal() as session:
                            from app.models.contact import Contact
                            from app.models.real_estate_agent import RealEstateAgent
                            from app.models.property import Property
                            from app.models.call import Call

                            # 0) Prefer pulling the call record to get contact_id → contact name/phone
                            try:
                                call_lookup = (
                                    await session.execute(
                                        select(Call)
                                        .options(selectinload(Call.contact))
                                        .where(Call.twilio_call_sid == call_sid)
                                        .limit(1)
                                    )
                                ).scalar_one_or_none()

                                if call_lookup and call_lookup.contact:
                                    contact_name = call_lookup.contact.name
                                    contact_phone = call_lookup.contact.phone_number
                                    logger.info(f"✅ Found contact via Call record: {contact_name}")
                            except Exception as call_lookup_error:
                                logger.warning(f"⚠️ Call record lookup failed: {call_lookup_error}")
                            
                            # Normalize to_number for lookup (for outbound, to_number is the contact)
                            normalized_to = to_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                            if not normalized_to.startswith("+"):
                                normalized_to = "+" + normalized_to
                            
                            logger.info(f"🔍 Looking up contact for phone: {normalized_to}, agent_id: {real_estate_agent_id}")
                            
                            # METHOD 1: Try Contact table by phone_number (skip if already found via call record)
                            if not contact_name:
                                # Normalize phone for matching (exact and last-10 fallback)
                                last10 = normalized_to[-10:] if len(normalized_to) > 10 else normalized_to
                                contact_stmt = (
                                    select(Contact)
                                    .where(
                                        Contact.real_estate_agent_id == real_estate_agent_id,
                                        or_(
                                            Contact.phone_number == normalized_to,
                                            Contact.phone_number.like(f"%{last10}%")
                                        )
                                    )
                                    .limit(1)
                                )
                                contact_result = await session.execute(contact_stmt)
                                contact = contact_result.scalar_one_or_none()
                                
                                if contact:
                                    contact_name = contact.name
                                    contact_phone = contact.phone_number
                                    logger.info(f"✅ Found contact via Contact table: {contact_name}")
                                    
                                    # Get first property for this contact (for context)
                                    property_stmt = select(Property).where(
                                        Property.contact_id == contact.id
                                    ).limit(1)
                                    property_result = await session.execute(property_stmt)
                                    property_obj = property_result.scalar_one_or_none()
                                    
                                    if property_obj:
                                        property_address = property_obj.address
                                        logger.info(f"✅ Found property: {property_address}")
                            
                            if not contact_name:
                                # METHOD 2: Try Property table by owner_phone, then get contact
                                logger.info(f"⚠️ Contact not found in Contact table, trying Property.owner_phone...")
                                property_stmt = select(Property).where(
                                    Property.owner_phone == normalized_to,
                                    Property.real_estate_agent_id == real_estate_agent_id
                                ).limit(1)
                                property_result = await session.execute(property_stmt)
                                property_obj = property_result.scalar_one_or_none()
                                
                                if property_obj:
                                    property_address = property_obj.address
                                    logger.info(f"✅ Found property via owner_phone: {property_address}")
                                    
                                    # Try to get contact from property.contact_id
                                    if property_obj.contact_id:
                                        contact_stmt = select(Contact).where(
                                            Contact.id == property_obj.contact_id
                                        ).limit(1)
                                        contact_result = await session.execute(contact_stmt)
                                        contact = contact_result.scalar_one_or_none()
                                        
                                        if contact:
                                            contact_name = contact.name
                                            logger.info(f"✅ Found contact via property.contact_id: {contact_name}")
                                        else:
                                            # Use owner_name from property as fallback
                                            contact_name = property_obj.owner_name
                                            logger.info(f"⚠️ Using property.owner_name as fallback: {contact_name}")
                                    else:
                                        # Use owner_name from property
                                        contact_name = property_obj.owner_name
                                        logger.info(f"⚠️ Using property.owner_name: {contact_name}")
                            
                            # Quick agent lookup
                            if real_estate_agent_id:
                                agent_stmt = select(RealEstateAgent).where(
                                    RealEstateAgent.id == real_estate_agent_id
                                ).limit(1)
                                agent_result = await session.execute(agent_stmt)
                                agent = agent_result.scalar_one_or_none()
                                
                                if agent:
                                    agent_name = agent.full_name
                                    company_name = agent.company_name or "Independent Agent"
                                    logger.info(f"✅ Found agent: {agent_name} from {company_name}")
                    except Exception as lookup_error:
                        logger.warning(f"⚠️ Quick lookup failed (non-critical): {lookup_error}", exc_info=True)
                        # Continue with LLM greeting using available info
                    
                    # Generate greeting using LLM with proper context
                    try:
                        from app.services.ai.prompt_service import get_initial_greeting_prompt
                        from app.services.ai.llm_service import generate_initial_greeting
                        
                        # Build context for greeting prompt
                        # CRITICAL: Always include contact name if available, even if empty dict
                        greeting_context = {
                            "voice_agent": {"name": voice_agent_name},
                            "real_estate_agent": {
                                "name": agent_name or "Real Estate Agent",
                                "company_name": company_name or "Independent Agent"
                            },
                            "contact": {"name": contact_name} if contact_name else {},  # Only include if we have name
                            "properties": [{"address": property_address}] if property_address else []
                        }
                        
                        # Log context for debugging
                        logger.info(f"📋 Greeting context - Contact: '{contact_name}' (type: {type(contact_name)}), Agent: {agent_name}, Company: {company_name}, Property: {property_address}")
                        
                        # CRITICAL: Verify contact_name is not None/empty before passing
                        if not contact_name or not contact_name.strip():
                            logger.warning(f"⚠️ Contact name is missing or empty! Contact lookup may have failed.")
                            logger.warning(f"⚠️ to_number: {to_number}, normalized_to: {normalized_to if 'normalized_to' in locals() else 'N/A'}, real_estate_agent_id: {real_estate_agent_id}")
                        
                        # Get greeting prompt with context
                        greeting_prompt = get_initial_greeting_prompt(greeting_context, "outbound")
                        
                        # Generate greeting with LLM (with short timeout to stay under 3s total)
                        logger.info(f"🤖 Generating greeting with LLM...")
                        greeting = await asyncio.wait_for(
                            generate_initial_greeting(greeting_prompt, timeout=2.0),
                            timeout=2.5
                        )
                        logger.info(f"✅ LLM generated greeting: {greeting[:50]}...")
                        
                    except asyncio.TimeoutError:
                        logger.warning("⏱️ LLM greeting timeout, using fallback")
                        # Fallback greeting (force personalization when we have the name)
                        if contact_name:
                            if agent_name and company_name:
                                greeting = (
                                    f"Hello, this is {voice_agent_name} from {company_name}. "
                                    f"I'm calling on behalf of {agent_name}. Am I contacting {contact_name}?"
                                )
                            else:
                                greeting = (
                                    f"Hello, this is {voice_agent_name}. Am I contacting {contact_name}? "
                                    f"I'm calling about your property{f' at {property_address}' if property_address else ''}."
                                )
                        else:
                            greeting = (
                                f"Hello, this is {voice_agent_name}. "
                                f"Am I speaking with the property owner? I'm calling about your property."
                            )
                            
                    except Exception as llm_error:
                        logger.warning(f"⚠️ LLM greeting error: {llm_error}, using fallback")
                        # Fallback greeting (force personalization when we have the name)
                        if contact_name:
                            if agent_name and company_name:
                                greeting = (
                                    f"Hello, this is {voice_agent_name} from {company_name}. "
                                    f"I'm calling on behalf of {agent_name}. Am I contacting {contact_name}?"
                                )
                            else:
                                greeting = (
                                    f"Hello, this is {voice_agent_name}. Am I contacting {contact_name}? "
                                    f"I'm calling about your property{f' at {property_address}' if property_address else ''}."
                                )
                        else:
                            greeting = (
                                f"Hello, this is {voice_agent_name}. "
                                f"Am I speaking with the property owner? I'm calling about your property."
                            )
                else:
                    # Inbound call greeting
                    greeting = f"Hello, this is {voice_agent_name}. Thank you for calling. How can I help you?"
                
                # Create conversation state (only if we have valid IDs)
                conversation_state = None
                if voice_agent_id and real_estate_agent_id:
                    try:
                        conversation_state = create_conversation_state(
                            call_sid=call_sid,
                            direction="outbound" if is_outbound else "inbound",
                            context={},
                            voice_agent_id=voice_agent_id,
                            real_estate_agent_id=real_estate_agent_id,
                            contact_id=None
                        )
                        logger.info(f"✅ Conversation state created for call {call_sid}")
                    except Exception as state_error:
                        logger.error(f"❌ Failed to create conversation state: {state_error}", exc_info=True)
                        print(f"❌ State creation error: {state_error}")
                        # Continue anyway - state creation is not critical for initial greeting
                else:
                    logger.warning(f"⚠️ Skipping conversation state creation - missing IDs: voice_agent_id={voice_agent_id}, real_estate_agent_id={real_estate_agent_id}")
                
                # Update conversation history (only if state exists)
                if conversation_state:
                    try:
                        update_conversation_history(call_sid, "assistant", greeting)
                    except Exception as history_error:
                        logger.warning(f"⚠️ Failed to update conversation history: {history_error}")
                        # Continue anyway - history update is not critical
                
                response.say(greeting, voice="alice")
                logger.info(f"✅ Added greeting to TwiML: {greeting[:50]}...")
        
        # Always gather speech
        gather = Gather(
            input="speech",
            action=voice_webhook_url,
            method="POST",
            timeout=5,
            speech_timeout="auto",
            language="en-US"
        )
        response.append(gather)
        
        # If no speech, redirect
        response.redirect(voice_webhook_url, method="POST")
        
        # ============================================================
        # PHASE 3: BACKGROUND TASKS (Non-blocking)
        # ============================================================
        
        # Log response time
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"⚡ Response generated in {elapsed:.3f}s")
            
        # Schedule background tasks (don't wait)
        asyncio.create_task(_background_tasks(
            call_sid=call_sid,
            is_outbound=is_outbound,
            from_number=from_number,
            to_number=to_number,
            voice_agent_id=voice_agent_id,
            real_estate_agent_id=real_estate_agent_id,
            is_continuation=is_continuation
        ))
        
        twiml_response = str(response)
        logger.info(f"✅ Generated TwiML response ({len(twiml_response)} bytes)")
        return twiml_response
        
    except Exception as e:
        # Catch ANY error and return valid TwiML
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"❌ CRITICAL ERROR in handle_voice_webhook: {e}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        logger.error(f"❌ Full traceback:\n{error_trace}")
        print(f"\n{'='*60}")
        print(f"❌ CRITICAL ERROR IN WEBHOOK HANDLER")
        print(f"Error: {e}")
        print(f"Type: {type(e).__name__}")
        print(f"Traceback:\n{error_trace}")
        print(f"{'='*60}\n")
        # Always return valid TwiML, even on error
        return _generate_error_twiml("an application error occurred. Please try again later.")


async def _background_tasks(
    call_sid: str,
    is_outbound: bool,
    from_number: str,
    to_number: str,
    voice_agent_id: str,
    real_estate_agent_id: str,
    is_continuation: bool
):
    """
    Execute non-critical tasks in background
    These don't block the webhook response
    """
    try:
        # Task 1: Create/update call record
        await _update_call_record(
            call_sid=call_sid,
            is_outbound=is_outbound,
            from_number=from_number,
            to_number=to_number,
            voice_agent_id=voice_agent_id,
            real_estate_agent_id=real_estate_agent_id
        )
        
        # Task 2: Build context (if not already built)
        if not is_continuation:
            await _build_context_background(
                call_sid=call_sid,
                is_outbound=is_outbound,
                from_number=from_number,
                voice_agent_id=voice_agent_id,
                real_estate_agent_id=real_estate_agent_id
            )
        
    except Exception as bg_error:
        logger.error(f"❌ Background task error: {bg_error}", exc_info=True)


async def _update_call_record(
    call_sid: str,
    is_outbound: bool,
    from_number: str,
    to_number: str,
    voice_agent_id: str,
    real_estate_agent_id: str
):
    """Create or update call record"""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Call).where(Call.twilio_call_sid == call_sid)
            result = await session.execute(stmt)
            call = result.scalar_one_or_none()
                    
            if not call and not is_outbound:  # Create for inbound calls
                call = Call(
                    id=str(uuid.uuid4()),
                    voice_agent_id=voice_agent_id,
                    real_estate_agent_id=real_estate_agent_id,
                    twilio_call_sid=call_sid,
                    from_number=from_number,
                    to_number=to_number,
                    status="in-progress",
                    direction="inbound",
                    started_at=datetime.utcnow()
                )
                session.add(call)
                await session.commit()
                logger.info(f"✅ Call record created: {call.id}")
            elif call:
                logger.info(f"✅ Call record exists: {call.id}")
                
    except Exception as e:
        logger.error(f"❌ Call record error: {e}")


async def _build_context_background(
    call_sid: str,
    is_outbound: bool,
    from_number: str,
    voice_agent_id: str,
    real_estate_agent_id: str
):
    """Build conversation context in background"""
    try:
        conversation_state = get_conversation_state(call_sid)
        if not conversation_state:
            return
        
        # Check if context already built
        if conversation_state.get("context") and conversation_state["context"]:
            logger.info(f"✅ Context already exists for {call_sid}")
            return
        
        logger.info(f"🔄 Building full context in background for {call_sid}")
        
        context = None
        contact_id = None
        
        if is_outbound:
            # Get contact_id from call record
            try:
                async with AsyncSessionLocal() as session:
                    stmt = select(Call.contact_id).where(Call.twilio_call_sid == call_sid)
                    result = await session.execute(stmt)
                    contact_id = result.scalar_one_or_none()
                    
                    if not contact_id:
                        logger.warning(f"⚠️ No contact_id found for outbound call {call_sid}")
                        return
                        
            except Exception as e:
                logger.warning(f"⚠️ Could not get contact_id: {e}")
                return
            
            # Build full context with contact, properties, etc.
            if contact_id:
                logger.info(f"🔄 Building outbound context for contact {contact_id}")
                context = await build_outbound_context(
                    contact_id=contact_id,
                    real_estate_agent_id=real_estate_agent_id,
                    voice_agent_id=voice_agent_id
                )
        else:
            # Inbound call - build context with all properties
            logger.info(f"🔄 Building inbound context for caller {from_number}")
            context = await build_inbound_context(
                real_estate_agent_id=real_estate_agent_id,
                voice_agent_id=voice_agent_id,
                caller_phone=from_number
            )
        
        # Update state with full context
        if context:
            conversation_state["context"] = context
            conversation_state["contact_id"] = contact_id
            logger.info(f"✅ Full context built for {call_sid} - Contact: {contact_id}")
        else:
            logger.warning(f"⚠️ Context building returned None for {call_sid}")
                    
    except Exception as e:
        logger.error(f"❌ Context building error for {call_sid}: {e}", exc_info=True)


def _generate_error_twiml(message: str) -> str:
    """Generate error TwiML response"""
    response = VoiceResponse()
    response.say(f"Sorry, {message}", voice="alice")
    response.hangup()
    return str(response)


def _history_to_text(history: list) -> Optional[str]:
    """Convert structured history to readable text transcript"""
    if not history:
        return None
    lines = []
    for item in history:
        role = item.get("role", "assistant")
        content = item.get("content", "")
        timestamp = item.get("timestamp")
        speaker = "Agent" if role == "assistant" else "User" if role == "user" else "System"
        if timestamp:
            try:
                ts = datetime.fromisoformat(timestamp)
                ts_str = ts.strftime("%H:%M:%S")
            except Exception:
                ts_str = ""
        else:
            ts_str = ""
        prefix = f"[{ts_str}] {speaker}:" if ts_str else f"{speaker}:"
        if content:
            lines.append(f"{prefix} {content}")
    return "\n".join(lines) if lines else None


def _parse_transcript_to_messages(transcript: str, direction: str = "outbound") -> list:
    """Fallback: parse plain text transcript into structured messages"""
    import re
    messages = []
    if not transcript:
        return messages
    sentences = re.split(r'[.!?]\s+|\n+', transcript.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    is_agent_turn = direction == "outbound"
    for sentence in sentences:
        if len(sentence) < 3:
            continue
        role = "assistant" if is_agent_turn else "user"
        messages.append({
            "role": role,
            "content": sentence,
            "timestamp": None
        })
        is_agent_turn = not is_agent_turn
    return messages


async def _generate_user_pov_summary(history: list, direction: str = "outbound") -> Optional[str]:
    """Generate a concise user POV summary (max 2 lines) using the LLM"""
    if not history:
        return None

    # If the user never spoke, don't fabricate a POV
    user_messages = [m for m in history if m.get("role") == "user" and (m.get("content") or "").strip()]
    if not user_messages:
        return None
    # Build prompt
    direction_text = "outbound (agent initiated)" if direction == "outbound" else "inbound (user initiated)"
    prompt = (
        f"You are summarizing a voice call from the USER'S point of view. "
        f"The call direction is {direction_text}. "
        "Write at most 2 short sentences capturing the user's intent, next steps, or key request. "
        "Be concise and actionable. Avoid fluff."
    )
    try:
        summary = await process_with_llm(
            user_input="Summarize the user POV in 2 short sentences.",
            system_prompt=prompt,
            conversation_history=history,
            max_tokens=80,
            temperature=0.3,
            timeout=6.0
        )
        # Clamp to 2 lines
        summary_lines = summary.strip().splitlines()
        summary = " ".join(summary_lines[:2]).strip()
        return summary
    except Exception as e:
        logger.warning(f"⚠️ User POV summary generation failed: {e}")
        # Fallback: use last user message
        last_user = next((m for m in reversed(history) if m.get("role") == "user" and m.get("content")), None)
        if last_user:
            return f"User intent: {last_user['content'][:180]}"
        return None


async def _persist_conversation_history_to_db(call_sid: str) -> None:
    """
    Persist in-memory conversation history to the DB (transcript + JSON + user POV)
    """
    try:
        # Get structured history from memory
        history = get_conversation_history(call_sid)
        
        # Fetch call to determine direction and fallback transcript
        async with AsyncSessionLocal() as session:
            stmt = select(Call).where(Call.twilio_call_sid == call_sid)
            result = await session.execute(stmt)
            call = result.scalar_one_or_none()
        
        if not call:
            return
        
        direction = call.direction or "outbound"
        
        # Fallback: parse existing transcript if no in-memory history
        if not history and call.transcript:
            history = _parse_transcript_to_messages(call.transcript, direction)
        
        transcript_text = _history_to_text(history) if history else call.transcript
        
        user_pov_summary = await _generate_user_pov_summary(history, direction) if history else None
        
        await save_transcript_by_twilio_sid(
            twilio_call_sid=call_sid,
            transcript=transcript_text,
            transcript_json=history if history else None,
            user_pov_summary=user_pov_summary
        )
    except Exception as e:
        logger.error(f"❌ Failed to persist conversation history for {call_sid}: {e}", exc_info=True)


async def handle_status_webhook(form_data: Dict) -> None:
    """Handle call status updates from Twilio"""
    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    call_duration = form_data.get("CallDuration", None)
    
    logger.info(f"📊 Status update - SID: {call_sid}, Status: {call_status}, Duration: {call_duration}s")
    
    try:
        from app.services.call_service import update_call_status
        
        duration = int(call_duration) if call_duration else None
        await update_call_status(
            twilio_call_sid=call_sid,
            status=call_status,
            duration=duration
        )
        
        # Clean up conversation state when call ends
        if call_status in ["completed", "failed", "busy", "no-answer", "canceled"]:
            # Persist conversation history before clearing
            await _persist_conversation_history_to_db(call_sid)
            clear_conversation_state(call_sid)
            logger.info(f"🧹 Cleared conversation state for {call_sid}")
            
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}", exc_info=True)


async def handle_recording_webhook(form_data: Dict) -> None:
    """Handle recording status updates from Twilio"""
    call_sid = form_data.get("CallSid", "")
    recording_url = form_data.get("RecordingUrl", "")
    recording_sid = form_data.get("RecordingSid", "")
    
    logger.info(f"📼 Recording - SID: {call_sid}, URL: {recording_url}")
    
    try:
        from app.services.call_service import save_recording
        
        if recording_url and recording_sid:
            await save_recording(
                twilio_call_sid=call_sid,
                recording_url=recording_url,
                recording_sid=recording_sid
            )
            logger.info(f"✅ Recording saved for {call_sid}")
            
    except Exception as e:
        logger.error(f"❌ Recording webhook error: {e}", exc_info=True)