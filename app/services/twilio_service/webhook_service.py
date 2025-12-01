"""
Twilio Webhook Service - Handle Twilio webhooks and voice flow
STT → LLM → TTS pipeline
"""
from typing import Dict, Optional
import httpx
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
    """
    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    call_sid = form_data.get("CallSid", "")
    speech_result = form_data.get("SpeechResult", "")
    digits = form_data.get("Digits", "")
    
    # Get voice agent by phone number
    async with AsyncSessionLocal() as session:
        # Find phone number
        phone_stmt = select(PhoneNumber).where(PhoneNumber.twilio_phone_number == to_number)
        phone_result = await session.execute(phone_stmt)
        phone = phone_result.scalar_one_or_none()
        
        if not phone:
            response = VoiceResponse()
            response.say("Sorry, the voice agent is not available.", voice="alice")
            response.hangup()
            return str(response)
        
        # Find voice agent
        stmt = select(VoiceAgent).where(VoiceAgent.phone_number_id == phone.id)
        result = await session.execute(stmt)
        voice_agent = result.scalar_one_or_none()
        
        if not voice_agent or voice_agent.status != "active":
            response = VoiceResponse()
            response.say("Sorry, the voice agent is not available.", voice="alice")
            response.hangup()
            return str(response)
        
        # Get or create call record
        call_stmt = select(Call).where(Call.twilio_call_sid == call_sid)
        call_result = await session.execute(call_stmt)
        call = call_result.scalar_one_or_none()
        
        response = VoiceResponse()
        
        # If this is the first interaction, play greeting
        if not speech_result and not digits:
            greeting = voice_agent.settings.get("greeting_message", "Hello! How can I help you today?")
            response.say(greeting, voice="alice")
            
            # Gather speech input
            gather = Gather(
                input="speech",
                action="/webhooks/twilio/voice",
                method="POST",
                speech_timeout="auto",
                language="en-US"
            )
            gather.say("Please speak your message.", voice="alice")
            response.append(gather)
            
            # If no input, say goodbye
            response.say("Thank you for calling. Goodbye!", voice="alice")
            response.hangup()
            
            return str(response)
        
        # Process speech input
        if speech_result:
            # Get system prompt
            system_prompt = voice_agent.system_prompt or "You are a helpful assistant."
            
            # Process with LLM
            try:
                llm_response = await process_with_llm(
                    user_input=speech_result,
                    system_prompt=system_prompt,
                    context={
                        "agent_name": voice_agent.name,
                        "call_sid": call_sid
                    }
                )
                
                # Save transcript if call exists
                if call:
                    call.transcript = f"{call.transcript or ''}\nUser: {speech_result}\nAssistant: {llm_response}".strip()
                    await session.commit()
                
                # Speak response
                response.say(llm_response, voice="alice")
                
                # Continue conversation
                gather = Gather(
                    input="speech",
                    action="/webhooks/twilio/voice",
                    method="POST",
                    speech_timeout="auto",
                    language="en-US"
                )
                gather.say("Is there anything else I can help you with?", voice="alice")
                response.append(gather)
                
                # Fallback
                response.say("Thank you for calling. Goodbye!", voice="alice")
                response.hangup()
                
            except Exception as e:
                # Error handling
                response.say("I'm sorry, I encountered an error. Please try again later.", voice="alice")
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

