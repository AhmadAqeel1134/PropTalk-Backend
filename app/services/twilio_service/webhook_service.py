"""
Twilio Webhook Service - Handle Twilio webhooks and voice flow
STT → LLM → TTS pipeline
"""
from typing import Dict, Optional
import httpx
import uuid
from datetime import datetime
from twilio.twiml.voice_response import VoiceResponse, Gather
from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.models.voice_agent import VoiceAgent
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from sqlalchemy import select


async def handle_voice_webhook(form_data: Dict) -> str:
    """
    Handle incoming voice webhook from Twilio
    Returns TwiML XML response
    IMPORTANT: Must be fast - Twilio expects response within 3 seconds
    """
    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    call_sid = form_data.get("CallSid", "")
    speech_result = form_data.get("SpeechResult", "")
    digits = form_data.get("Digits", "")
    direction = form_data.get("Direction", "")
    
    # Determine which number to look up based on call direction
    # For outbound calls: From = Twilio number (in DB), To = end user (not in DB)
    # For inbound calls: To = Twilio number (in DB), From = caller (not in DB)
    twilio_number = None
    is_outbound = direction.startswith("outbound")  # Handles "outbound-api", "outbound-dial", etc.
    if is_outbound:
        twilio_number = from_number  # Twilio number is the "From" for outbound calls
        print(f"📞 Outbound call detected (Direction: {direction}) - Using From number as Twilio number: {twilio_number}")
    else:
        twilio_number = to_number  # Twilio number is the "To" for inbound calls
        print(f"📞 Inbound call detected (Direction: {direction}) - Using To number as Twilio number: {twilio_number}")
    
    # Get voice agent by phone number - optimized queries
    # Handle DB failures gracefully - always return valid TwiML
    voice_agent = None
    call = None
    # Extract voice agent data to avoid lazy loading after session closes
    voice_agent_id = None
    voice_agent_name = None
    voice_agent_system_prompt = None
    voice_agent_settings = {}
    real_estate_agent_id = None
    
    try:
        async with AsyncSessionLocal() as session:
            try:
                # Find phone number (indexed query - should be fast)
                # Normalize phone number for lookup (remove spaces, ensure + prefix)
                normalized_twilio_number = twilio_number.strip().replace(" ", "").replace("-", "")
                if not normalized_twilio_number.startswith("+"):
                    normalized_twilio_number = "+" + normalized_twilio_number
                
                print(f"🔍 Looking up Twilio phone number: {normalized_twilio_number} (original: {twilio_number})")
                print(f"📋 Full call context - From: {from_number}, To: {to_number}, Direction: {direction}, CallSid: {call_sid}")
                
                # Combined query: Get phone number and voice agent in one JOIN query (faster - single DB round trip)
                from sqlalchemy.orm import aliased
                va_alias = aliased(VoiceAgent)
                combined_stmt = (
                    select(PhoneNumber, va_alias)
                    .outerjoin(va_alias, PhoneNumber.id == va_alias.phone_number_id)
                    .where(PhoneNumber.twilio_phone_number == normalized_twilio_number)
                )
                combined_result = await session.execute(combined_stmt)
                result_row = combined_result.first()
                
                # If not found, try with original format
                if not result_row and normalized_twilio_number != twilio_number:
                    print(f"🔍 Retrying lookup with original format: {twilio_number}")
                    combined_stmt = (
                        select(PhoneNumber, va_alias)
                        .outerjoin(va_alias, PhoneNumber.id == va_alias.phone_number_id)
                        .where(PhoneNumber.twilio_phone_number == twilio_number)
                    )
                    combined_result = await session.execute(combined_stmt)
                    result_row = combined_result.first()
                
                if not result_row:
                    print(f"❌ Twilio phone number not found in database: {twilio_number}")
                    response = VoiceResponse()
                    response.say("Sorry, the voice agent is not available.", voice="alice")
                    response.hangup()
                    return str(response)
                
                phone = result_row[0]
                voice_agent = result_row[1]
                
                print(f"✅ Phone number found: {phone.twilio_phone_number} (ID: {phone.id}, Active: {phone.is_active})")
                
                if not voice_agent:
                    print(f"❌ Voice agent not found for phone_number_id: {phone.id}")
                    response = VoiceResponse()
                    response.say("Sorry, the voice agent is not available.", voice="alice")
                    response.hangup()
                    return str(response)
                
                if voice_agent.status != "active":
                    print(f"❌ Voice agent found but status is '{voice_agent.status}', not 'active'")
                    print(f"   Voice Agent: {voice_agent.name} (ID: {voice_agent.id}, Status: {voice_agent.status})")
                    
                    response = VoiceResponse()
                    response.say("Sorry, the voice agent is not available.", voice="alice")
                    response.hangup()
                    return str(response)
                
                print(f"✅ Voice agent found: {voice_agent.name} (ID: {voice_agent.id}, Status: {voice_agent.status})")
                
                # Extract voice agent data BEFORE closing session (to avoid lazy loading delays)
                voice_agent_id = voice_agent.id
                voice_agent_name = voice_agent.name
                voice_agent_system_prompt = voice_agent.system_prompt
                voice_agent_settings = voice_agent.settings or {}
                real_estate_agent_id = voice_agent.real_estate_agent_id
                
            except Exception as db_error:
                # If DB query fails, log and return fallback response
                import logging
                import traceback
                logger = logging.getLogger(__name__)
                error_trace = traceback.format_exc()
                logger.error(f"Database error in webhook handler: {db_error}", exc_info=True)
                print(f"⚠️ Database error: {db_error}")
                print(f"📋 Error traceback:\n{error_trace}")
                print(f"📋 Call details - From: {from_number}, To: {to_number}, Direction: {direction}, Twilio Number: {twilio_number}")
                # Return a basic response so call can proceed
                response = VoiceResponse()
                response.say("Hello, thank you for calling. Please hold while we connect you.", voice="alice")
                # Redirect to retry
                webhook_base_url = settings.TWILIO_VOICE_WEBHOOK_URL or ""
                voice_webhook_url = f"{webhook_base_url}/webhooks/twilio/voice" if webhook_base_url else "/webhooks/twilio/voice"
                response.redirect(voice_webhook_url, method="POST")
                return str(response)
        
        # CLOSE SESSION BEFORE generating TwiML - this ensures no DB operations block the response
        # Now generate TwiML IMMEDIATELY - don't wait for call record operations
        # This is critical to respond within Twilio's 3-second timeout
        
        # Safety check - should never happen but just in case
        if not voice_agent_id:
            response = VoiceResponse()
            response.say("Sorry, the voice agent is not available.", voice="alice")
            response.hangup()
            return str(response)
        
        response = VoiceResponse()
        
        # Get webhook base URL for Gather actions
        webhook_base_url = settings.TWILIO_VOICE_WEBHOOK_URL or ""
        voice_webhook_url = f"{webhook_base_url}/webhooks/twilio/voice" if webhook_base_url else "/webhooks/twilio/voice"
        
        # Schedule call record update in background (non-blocking)
        # Use asyncio.create_task to run it without blocking the response
        import asyncio
        async def update_call_record_background():
            try:
                async with AsyncSessionLocal() as bg_session:
                    call_stmt = select(Call).where(Call.twilio_call_sid == call_sid)
                    call_result = await bg_session.execute(call_stmt)
                    call = call_result.scalar_one_or_none()
                    
                    # Create call record if it doesn't exist (for inbound calls only - outbound already exists)
                    if not call and not is_outbound:  # Outbound calls already have records
                        normalized_direction = "inbound"
                        call_id = str(uuid.uuid4())
                        call = Call(
                            id=call_id,
                            voice_agent_id=voice_agent_id,
                            real_estate_agent_id=real_estate_agent_id,
                            twilio_call_sid=call_sid,
                            from_number=from_number,
                            to_number=to_number,
                            status="in-progress",
                            direction=normalized_direction,
                            started_at=datetime.utcnow()
                        )
                        bg_session.add(call)
                        await bg_session.commit()
                        print(f"✅ Call record created: {call_id} (Direction: {normalized_direction})")
                    elif call:
                        print(f"✅ Call record found: {call.id}")
            except Exception as db_error:
                # If call record creation fails, log but continue (non-critical)
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to create/update call record: {db_error}")
                print(f"⚠️ Call record creation failed (non-critical): {db_error}")
        
        # Start background task but don't wait for it
        # Wrap in try-except to ensure it doesn't block the response
        try:
            asyncio.create_task(update_call_record_background())
        except Exception as task_error:
            # Log but don't fail - background task is non-critical
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create background task: {task_error}")
            print(f"⚠️ Background task creation failed (non-critical): {task_error}")
        
        # Simple call handling - just greeting message, no STT/TTS/LLM
        # This is for basic inbound/outbound call pipeline testing
        
        # Get greeting message from voice agent settings
        greeting = voice_agent_settings.get("greeting_message", "Hello, thank you for calling PropTalk. How can I help you today?")
        
        # Play greeting
        response.say(greeting, voice="alice")
        
        # Simple follow-up message
        response.say("This is a test call. The call pipeline is working correctly.", voice="alice")
        
        # Thank you and hangup
        response.say("Thank you for calling. Goodbye!", voice="alice")
        response.hangup()
        
        # Return TwiML immediately
        print(f"✅ Generated simple greeting TwiML for {direction} call")
        return str(response)
    except Exception as e:
        # If anything fails, return a simple error response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in handle_voice_webhook: {str(e)}", exc_info=True)
        response = VoiceResponse()
        response.say("Sorry, an error occurred. Please try again later.", voice="alice")
        response.hangup()
        return str(response)


async def handle_status_webhook(form_data: Dict) -> None:
    """Handle call status updates from Twilio"""
    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    call_duration = form_data.get("CallDuration", None)
    
    from app.services.call_service import update_call_status
    
    duration = int(call_duration) if call_duration else None
    await update_call_status(
        twilio_call_sid=call_sid,
        status=call_status,
        duration=duration
    )


async def handle_recording_webhook(form_data: Dict) -> None:
    """Handle recording status updates from Twilio"""
    call_sid = form_data.get("CallSid", "")
    recording_url = form_data.get("RecordingUrl", "")
    recording_sid = form_data.get("RecordingSid", "")
    
    from app.services.call_service import save_recording
    
    if recording_url and recording_sid:
        await save_recording(
            twilio_call_sid=call_sid,
            recording_url=recording_url,
            recording_sid=recording_sid
        )


async def process_speech_to_text(audio_url: str) -> str:
    """
    Convert speech to text using OpenAI Whisper API
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OpenAI API key not configured")
    
    async with httpx.AsyncClient() as client:
        # Download audio from Twilio
        audio_response = await client.get(audio_url)
        audio_data = audio_response.content
        
        # Transcribe with OpenAI Whisper
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        data = {"model": "whisper-1"}
        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        
        response = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            files=files,
            data=data,
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise ValueError(f"OpenAI API error: {response.text}")
        
        result = response.json()
        return result.get("text", "")


async def process_with_llm(
    user_input: str,
    system_prompt: str,
    context: Optional[Dict] = None
) -> str:
    """
    Process user input with OpenAI GPT
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OpenAI API key not configured")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise ValueError(f"OpenAI API error: {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()


async def text_to_speech(text: str, voice_settings: Dict) -> str:
    """
    Convert text to speech using OpenAI TTS API
    Returns audio URL (or we can use Twilio's built-in TTS)
    For now, we'll use Twilio's built-in TTS in TwiML
    """
    # Twilio has built-in TTS, so we don't need OpenAI TTS
    # We'll use Twilio's <Say> verb in TwiML
    # This function is here for future use if needed
    pass

