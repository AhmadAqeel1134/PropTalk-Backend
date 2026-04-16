"""
Call Service - Business logic for call management
Handles call initiation, recording, and history
"""
import asyncio
import logging
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import uuid
from sqlalchemy import select, and_, or_, func, desc, literal
from sqlalchemy.orm import selectinload
from app.database.connection import AsyncSessionLocal
from app.models.call import Call
from app.models.voice_agent import VoiceAgent
from app.models.contact import Contact
from app.services.twilio_service.client import get_twilio_client
from app.services.sentiment_service import analyze_sentiment, text_for_sentiment
from app.config import settings

logger = logging.getLogger(__name__)


async def _persist_call_sentiment(
    call_id: str,
    sentiment_label: str,
    sentiment_scores: Optional[Dict[str, Any]],
) -> None:
    async with AsyncSessionLocal() as session:
        stmt = select(Call).where(Call.id == call_id)
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        if not call:
            return
        call.sentiment_label = sentiment_label
        call.sentiment_scores = sentiment_scores
        await session.commit()


async def enrich_calls_with_sentiment(items: List[Dict]) -> List[Dict]:
    """
    For calls with user_pov_summary and no stored sentiment, call external sentiment API
    (user-only text), persist result, and attach to dicts. Bounded concurrency.
    """
    if not items:
        return items
    if not getattr(settings, "SENTIMENT_ENABLED", True):
        return items

    sem = asyncio.Semaphore(3)

    async def process_one(d: Dict) -> None:
        if not d.get("user_pov_summary"):
            return
        if d.get("sentiment_label"):
            return
        text = text_for_sentiment(
            d.get("user_pov_summary"),
            d.get("transcript_json"),
            d.get("transcript"),
        )
        if not text:
            return
        async with sem:
            res = await analyze_sentiment(text)
        if not res:
            return
        label = res["sentiment"]
        scores = res.get("scores")
        await _persist_call_sentiment(d["id"], label, scores)
        d["sentiment_label"] = label
        d["sentiment_scores"] = scores or {}

    await asyncio.gather(*[process_one(d) for d in items])
    return items


async def initiate_call(
    real_estate_agent_id: str,
    contact_id: Optional[str],
    phone_number: str
) -> Dict:
    """Initiate an outbound call via Twilio"""
    print(f"🔍 Looking up voice agent for agent ID: {real_estate_agent_id}")
    logger.info(f"Initiating call - Agent: {real_estate_agent_id}, To: {phone_number}, Contact: {contact_id}")
    
    async with AsyncSessionLocal() as session:
        # Get voice agent
        stmt = (
            select(VoiceAgent)
            .options(selectinload(VoiceAgent.phone_number))
            .where(
                and_(
                    VoiceAgent.real_estate_agent_id == real_estate_agent_id,
                    VoiceAgent.status == "active"
                )
            )
        )
        result = await session.execute(stmt)
        voice_agent = result.scalar_one_or_none()
        
        if not voice_agent:
            print("❌ No active voice agent found")
            logger.error(f"No active voice agent found for agent: {real_estate_agent_id}")
            raise ValueError("Active voice agent not found")
        
        print(f"✅ Voice agent found: {voice_agent.name} (ID: {voice_agent.id})")
        logger.info(f"Voice agent found: {voice_agent.id}")
        
        if not voice_agent.phone_number:
            print("❌ Voice agent has no phone number assigned")
            logger.error(f"Voice agent {voice_agent.id} has no phone number assigned")
            raise ValueError("Voice agent does not have a phone number assigned")
        
        print(f"📞 Voice agent phone number: {voice_agent.phone_number.twilio_phone_number}")
        logger.info(f"Voice agent phone: {voice_agent.phone_number.twilio_phone_number}")
        
        # Get contact if provided
        contact = None
        if contact_id:
            contact_stmt = select(Contact).where(
                and_(
                    Contact.id == contact_id,
                    Contact.real_estate_agent_id == real_estate_agent_id
                )
            )
            contact_result = await session.execute(contact_stmt)
            contact = contact_result.scalar_one_or_none()
            
            if contact:
                # Use contact's phone number if contact is provided
                phone_number = contact.phone_number
                print(f"📇 Using contact phone number: {phone_number}")
                logger.info(f"Using contact phone number: {phone_number}")
        
        # Normalize phone number (ensure E.164 format)
        original_phone = phone_number
        
        # Remove all non-digit characters except +
        cleaned = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        # Ensure it starts with +
        if not cleaned.startswith("+"):
            # If starts with country code 92, add +
            if cleaned.startswith("92"):
                cleaned = "+" + cleaned
            # If starts with 0 (Pakistan local format), replace with +92
            elif cleaned.startswith("0"):
                cleaned = "+92" + cleaned[1:]
            # Otherwise, assume Pakistan and add +92
            else:
                cleaned = "+92" + cleaned
        else:
            # Already has +, but check for double country code
            # If it's +92 followed by 92 again, remove the duplicate
            if cleaned.startswith("+9292"):
                cleaned = "+92" + cleaned[5:]
        
        phone_number = cleaned
        
        if phone_number != original_phone:
            print(f"📝 Normalized phone number: {original_phone} → {phone_number}")
            logger.info(f"Normalized phone number: {original_phone} → {phone_number}")
        
        # Validate phone number format (basic check)
        # E.164 format: + followed by 1-15 digits
        if not phone_number.startswith("+") or len(phone_number) < 8 or len(phone_number) > 16:
            error_msg = f"Invalid phone number format: {phone_number}. Expected E.164 format (e.g., +923001234567 or +1234567890)"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Check for digits after +
        digits_after_plus = phone_number[1:]
        if not digits_after_plus.isdigit():
            error_msg = f"Invalid phone number format: {phone_number}. Phone number should contain only digits after the + sign"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Create call record
        call_id = str(uuid.uuid4())
        print(f"📝 Creating call record - Call ID: {call_id}")
        logger.info(f"Creating call record - ID: {call_id}, To: {phone_number}")
        
        new_call = Call(
            id=call_id,
            voice_agent_id=voice_agent.id,
            real_estate_agent_id=real_estate_agent_id,
            # Use a temporary unique value for twilio_call_sid to satisfy unique constraint,
            # then overwrite it with the real Twilio SID once the API call succeeds.
            twilio_call_sid=call_id,
            contact_id=contact_id,
            from_number=voice_agent.phone_number.twilio_phone_number,
            to_number=phone_number,
            status="initiated",
            direction="outbound",
            started_at=datetime.utcnow()
        )
        
        session.add(new_call)
        await session.commit()
        print(f"✅ Call record created in database")
        logger.info(f"Call record created - ID: {call_id}")
        
        # Make call via Twilio
        try:
            print(f"🔌 Connecting to Twilio API...")
            client = get_twilio_client()
            
            # Get webhook URL from settings
            base_url = settings.TWILIO_VOICE_WEBHOOK_URL
            if not base_url:
                print("❌ TWILIO_VOICE_WEBHOOK_URL not configured")
                logger.error("TWILIO_VOICE_WEBHOOK_URL not configured in environment")
                raise ValueError("TWILIO_VOICE_WEBHOOK_URL not configured in environment")
            
            voice_url = f"{base_url}/webhooks/twilio/voice"
            recording_callback = f"{base_url}/webhooks/twilio/recording"
            
            print(f"📞 Calling Twilio API to initiate call...")
            print(f"   From: {voice_agent.phone_number.twilio_phone_number}")
            print(f"   To: {phone_number}")
            print(f"   Webhook URL: {voice_url}")
            logger.info(f"Calling Twilio API - From: {voice_agent.phone_number.twilio_phone_number}, To: {phone_number}, Webhook: {voice_url}")
            
            call = client.calls.create(
                to=phone_number,
                from_=voice_agent.phone_number.twilio_phone_number,
                url=voice_url,
                method="POST",
                record=True,  # Enable recording
                recording_status_callback=recording_callback,
                recording_status_callback_method="POST",
                status_callback=f"{base_url}/webhooks/twilio/status",
                status_callback_method="POST"
            )
            
            print(f"✅ Twilio call created successfully!")
            print(f"   Twilio Call SID: {call.sid}")
            print(f"   Call Status: {call.status}")
            logger.info(f"Twilio call created - SID: {call.sid}, Status: {call.status}")
            
            # Update call with Twilio SID
            new_call.twilio_call_sid = call.sid
            await session.commit()
            await session.refresh(new_call)
            print(f"✅ Call record updated with Twilio SID")
            
            result = {
                "id": new_call.id,
                "twilio_call_sid": call.sid,
                "status": "initiated",
                "to_number": phone_number,
                "from_number": voice_agent.phone_number.twilio_phone_number,
            }
            
            return result
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ ERROR: Failed to initiate Twilio call")
            print(f"   Error: {error_msg}")
            print(f"   Error Type: {type(e).__name__}\n")
            logger.error(f"Failed to initiate Twilio call - Error: {error_msg}", exc_info=True)
            
            # Update call status to failed
            new_call.status = "failed"
            await session.commit()
            raise ValueError(f"Failed to initiate call: {error_msg}")


async def initiate_batch_calls(
    real_estate_agent_id: str,
    contact_ids: List[str],
    delay_seconds: int = 30
) -> Dict:
    """Initiate batch calls with delay between each"""
    import asyncio
    
    calls = []
    errors = []
    
    # Minimum delay of 3 seconds to prevent webhook conflicts and timeouts
    # This ensures webhooks have time to process before next call
    # Webhooks need ~2-3 seconds to process, so we need at least that much delay
    actual_delay = max(delay_seconds, 3) if delay_seconds >= 0 else 3
    if delay_seconds < 3:
        print(f"⚠️ Delay of {delay_seconds}s is too short. Using minimum 3s delay to prevent webhook conflicts.")
    
    for i, contact_id in enumerate(contact_ids):
        try:
            # Get contact phone number
            async with AsyncSessionLocal() as session:
                stmt = select(Contact).where(
                    and_(
                        Contact.id == contact_id,
                        Contact.real_estate_agent_id == real_estate_agent_id
                    )
                )
                result = await session.execute(stmt)
                contact = result.scalar_one_or_none()
                
                if not contact:
                    errors.append({"contact_id": contact_id, "error": "Contact not found"})
                    continue
                
                # Initiate call
                call_data = await initiate_call(
                    real_estate_agent_id=real_estate_agent_id,
                    contact_id=contact_id,
                    phone_number=contact.phone_number
                )
                calls.append(call_data)
                
                # Delay before next call (except for last one)
                # Use actual_delay to ensure minimum 2 seconds between calls
                if i < len(contact_ids) - 1:
                    print(f"⏱️ Waiting {actual_delay} seconds before next call...")
                    await asyncio.sleep(actual_delay)
        except Exception as e:
            logger.error(f"Error initiating call for contact {contact_id}: {str(e)}", exc_info=True)
            errors.append({"contact_id": contact_id, "error": str(e)})
    
    return {
        "call_count": len(calls),
        "calls": calls,
        "errors": errors
    }


async def get_calls_by_agent(
    real_estate_agent_id: str,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    direction: Optional[str] = None,
    search: Optional[str] = None
) -> Tuple[List[Dict], int]:
    """Get paginated calls for an agent with server-side filtering and search"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import or_
        from app.models.contact import Contact
        
        # Build query with joins for search
        conditions = [Call.real_estate_agent_id == real_estate_agent_id]
        
        if status:
            conditions.append(Call.status == status)
        if direction:
            conditions.append(Call.direction == direction)
        
        # Build search conditions separately to include contact name search
        if search:
            search_pattern = f"%{search}%"
            # Search in phone numbers and contact name
            search_conditions = or_(
                Call.from_number.ilike(search_pattern),
                Call.to_number.ilike(search_pattern),
                Contact.name.ilike(search_pattern),
                Contact.phone_number.ilike(search_pattern)
            )
            # Combine with existing conditions
            final_where = and_(*conditions, search_conditions)
            
            # Count query with contact join for search
            count_stmt = (
                select(func.count(Call.id))
                .select_from(Call)
                .outerjoin(Contact, Call.contact_id == Contact.id)
                .where(final_where)
            )
            
            # Paginated query with contact join for search
            stmt = (
                select(Call)
                .outerjoin(Contact, Call.contact_id == Contact.id)
                .options(
                    selectinload(Call.contact),
                    selectinload(Call.voice_agent).selectinload(VoiceAgent.phone_number)
                )
                .where(final_where)
                .order_by(desc(Call.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
        else:
            where_clause = and_(*conditions)
            
            # Count query without search
            count_stmt = select(func.count(Call.id)).select_from(Call).where(where_clause)
            
            # Paginated query without search
            stmt = (
                select(Call)
                .options(
                    selectinload(Call.contact),
                    selectinload(Call.voice_agent).selectinload(VoiceAgent.phone_number)
                )
                .where(where_clause)
                .order_by(desc(Call.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
        
        # Execute count query
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one() or 0
        
        result = await session.execute(stmt)
        calls = result.scalars().all()
        
        items = [
            {
                "id": call.id,
                "voice_agent_id": call.voice_agent_id,
                "voice_agent_name": call.voice_agent.name if call.voice_agent else None,
                "real_estate_agent_id": call.real_estate_agent_id,
                "twilio_call_sid": call.twilio_call_sid,
                "contact_id": call.contact_id,
                "contact_name": call.contact.name if call.contact else None,
                "contact_phone": call.contact.phone_number if call.contact else None,
                "from_number": call.from_number,
                "to_number": call.to_number,
                "twilio_phone_number": call.voice_agent.phone_number.twilio_phone_number if call.voice_agent and call.voice_agent.phone_number else None,
                "status": call.status,
                "direction": call.direction,
                "duration_seconds": call.duration_seconds,
                "recording_url": call.recording_url,
                "recording_sid": call.recording_sid,
                "transcript": call.transcript,
                "transcript_json": call.transcript_json,
                "user_pov_summary": call.user_pov_summary,
                "sentiment_label": call.sentiment_label,
                "sentiment_scores": call.sentiment_scores,
                "started_at": call.started_at.isoformat() if call.started_at else None,
                "answered_at": call.answered_at.isoformat() if call.answered_at else None,
                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                "created_at": call.created_at.isoformat() if call.created_at else "",
                "updated_at": call.updated_at.isoformat() if call.updated_at else "",
            }
            for call in calls
        ]

        items = await enrich_calls_with_sentiment(items)
        return items, total


async def get_call_by_id(call_id: str, real_estate_agent_id: str) -> Optional[Dict]:
    """Get a specific call by ID with proper joins"""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Call)
            .options(
                selectinload(Call.contact),
                selectinload(Call.voice_agent).selectinload(VoiceAgent.phone_number)
            )
            .where(
                and_(
                    Call.id == call_id,
                    Call.real_estate_agent_id == real_estate_agent_id
                )
            )
        )
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            return None
        
        row = {
            "id": call.id,
            "voice_agent_id": call.voice_agent_id,
            "voice_agent_name": call.voice_agent.name if call.voice_agent else None,
            "real_estate_agent_id": call.real_estate_agent_id,
            "twilio_call_sid": call.twilio_call_sid,
            "contact_id": call.contact_id,
            "contact_name": call.contact.name if call.contact else None,
            "contact_phone": call.contact.phone_number if call.contact else None,
            "from_number": call.from_number,
            "to_number": call.to_number,
            "twilio_phone_number": call.voice_agent.phone_number.twilio_phone_number if call.voice_agent and call.voice_agent.phone_number else None,
            "status": call.status,
            "direction": call.direction,
            "duration_seconds": call.duration_seconds,
            "recording_url": call.recording_url,
            "recording_sid": call.recording_sid,
            "transcript": call.transcript,
            "transcript_json": call.transcript_json,
            "user_pov_summary": call.user_pov_summary,
            "sentiment_label": call.sentiment_label,
            "sentiment_scores": call.sentiment_scores,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "answered_at": call.answered_at.isoformat() if call.answered_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "created_at": call.created_at.isoformat() if call.created_at else "",
            "updated_at": call.updated_at.isoformat() if call.updated_at else "",
        }
        enriched = await enrich_calls_with_sentiment([row])
        return enriched[0] if enriched else None


async def update_call_status(
    twilio_call_sid: str,
    status: str,
    duration: Optional[int] = None
) -> Optional[Dict]:
    """Update call status from Twilio webhook"""
    async with AsyncSessionLocal() as session:
        stmt = select(Call).where(Call.twilio_call_sid == twilio_call_sid)
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            return None
        
        call.status = status
        
        # Update timestamps based on status
        now = datetime.utcnow()
        if status == "in-progress" and not call.answered_at:
            call.answered_at = now
        elif status in ["completed", "failed", "busy", "no-answer"]:
            call.ended_at = now
        
        if duration is not None:
            call.duration_seconds = duration
        
        await session.commit()
        await session.refresh(call)
        
        return {
            "id": call.id,
            "status": call.status,
            "duration_seconds": call.duration_seconds,
        }


async def save_recording(
    twilio_call_sid: str,
    recording_url: str,
    recording_sid: str
) -> Optional[Dict]:
    """Save recording URL from Twilio webhook"""
    async with AsyncSessionLocal() as session:
        stmt = select(Call).where(Call.twilio_call_sid == twilio_call_sid)
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            return None
        
        call.recording_url = recording_url
        call.recording_sid = recording_sid
        
        await session.commit()
        await session.refresh(call)
        
        return {
            "id": call.id,
            "recording_url": call.recording_url,
            "recording_sid": call.recording_sid,
        }


async def save_transcript(
    call_id: str,
    transcript: str,
    transcript_json: Optional[List[Dict]] = None,
    user_pov_summary: Optional[str] = None
) -> Optional[Dict]:
    """Save transcript and structured history for a call"""
    async with AsyncSessionLocal() as session:
        stmt = select(Call).where(Call.id == call_id)
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            return None
        
        call.transcript = transcript
        call.transcript_json = transcript_json
        call.user_pov_summary = user_pov_summary
        await session.commit()
        
        return {
            "id": call.id,
            "transcript": call.transcript,
            "transcript_json": call.transcript_json,
            "user_pov_summary": call.user_pov_summary,
        }


async def save_transcript_by_twilio_sid(
    twilio_call_sid: str,
    transcript: Optional[str],
    transcript_json: Optional[List[Dict]] = None,
    user_pov_summary: Optional[str] = None
) -> Optional[Dict]:
    """Save transcript and structured history using the Twilio Call SID"""
    async with AsyncSessionLocal() as session:
        stmt = select(Call).where(Call.twilio_call_sid == twilio_call_sid)
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            return None
        
        call.transcript = transcript
        call.transcript_json = transcript_json
        call.user_pov_summary = user_pov_summary
        
        await session.commit()
        
        return {
            "id": call.id,
            "transcript": call.transcript,
            "transcript_json": call.transcript_json,
            "user_pov_summary": call.user_pov_summary,
        }


def _end_user_phone_match(user_digits: str):
    """
    Match Twilio E.164 or local-style numbers to the end user's saved digits.

    Exact digit match first; also match last 10 digits so +923038099142, 923038099142,
    and 03038099142-style inputs align with how contacts/calls are stored.
    """
    cleaned = "".join(c for c in (user_digits or "") if c.isdigit())
    if len(cleaned) < 10:
        return literal(False)
    suffix = cleaned[-10:]
    fn = func.regexp_replace(Call.from_number, "[^0-9]", "", "g")
    tn = func.regexp_replace(Call.to_number, "[^0-9]", "", "g")
    return or_(
        fn == cleaned,
        tn == cleaned,
        func.right(fn, 10) == suffix,
        func.right(tn, 10) == suffix,
    )


def _call_to_row(call: Call) -> Dict:
    return {
        "id": call.id,
        "voice_agent_id": call.voice_agent_id,
        "voice_agent_name": call.voice_agent.name if call.voice_agent else None,
        "real_estate_agent_id": call.real_estate_agent_id,
        "twilio_call_sid": call.twilio_call_sid,
        "contact_id": call.contact_id,
        "contact_name": call.contact.name if call.contact else None,
        "contact_phone": call.contact.phone_number if call.contact else None,
        "from_number": call.from_number,
        "to_number": call.to_number,
        "twilio_phone_number": (
            call.voice_agent.phone_number.twilio_phone_number
            if call.voice_agent and call.voice_agent.phone_number
            else None
        ),
        "status": call.status,
        "direction": call.direction,
        "duration_seconds": call.duration_seconds,
        "recording_url": call.recording_url,
        "recording_sid": call.recording_sid,
        "transcript": call.transcript,
        "transcript_json": call.transcript_json,
        "user_pov_summary": call.user_pov_summary,
        "sentiment_label": call.sentiment_label,
        "sentiment_scores": call.sentiment_scores,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "answered_at": call.answered_at.isoformat() if call.answered_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "created_at": call.created_at.isoformat() if call.created_at else "",
        "updated_at": call.updated_at.isoformat() if call.updated_at else "",
    }


async def list_calls_for_agent_and_user_phone(
    real_estate_agent_id: str,
    user_phone_digits: str,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Dict], int]:
    """Calls where the end user's phone matches from_number or to_number (same agent)."""
    async with AsyncSessionLocal() as session:
        base = and_(
            Call.real_estate_agent_id == real_estate_agent_id,
            _end_user_phone_match(user_phone_digits),
        )
        count_stmt = select(func.count(Call.id)).select_from(Call).where(base)
        total = (await session.execute(count_stmt)).scalar_one() or 0

        stmt = (
            select(Call)
            .options(
                selectinload(Call.contact),
                selectinload(Call.voice_agent).selectinload(VoiceAgent.phone_number),
            )
            .where(base)
            .order_by(desc(Call.created_at))
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        calls = result.scalars().all()
        items = [_call_to_row(c) for c in calls]
        items = await enrich_calls_with_sentiment(items)
        return items, total


async def get_call_by_id_for_agent_and_user_phone(
    call_id: str,
    real_estate_agent_id: str,
    user_phone_digits: str,
) -> Optional[Dict]:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Call)
            .options(
                selectinload(Call.contact),
                selectinload(Call.voice_agent).selectinload(VoiceAgent.phone_number),
            )
            .where(
                and_(
                    Call.id == call_id,
                    Call.real_estate_agent_id == real_estate_agent_id,
                    _end_user_phone_match(user_phone_digits),
                )
            )
        )
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        if not call:
            return None
        row = _call_to_row(call)
        enriched = await enrich_calls_with_sentiment([row])
        return enriched[0] if enriched else None


async def fetch_twilio_recording_bytes(recording_url: str) -> Tuple[bytes, str]:
    """
    Download recording from Twilio (Basic auth). Returns (body, content_type).
    Used by agent and end-user recording proxies.
    """
    import base64
    import httpx

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise ValueError("Twilio credentials not configured")

    credentials = f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded_credentials}"

    twilio_url = recording_url
    if not twilio_url.endswith((".mp3", ".wav", ".m4a")):
        if "api.twilio.com" in twilio_url and "/Recordings/" in twilio_url:
            twilio_url = f"{recording_url}.mp3"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            twilio_url,
            headers={
                "Authorization": auth_header,
                "Accept": "audio/mpeg, audio/mp3, */*",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Twilio recording HTTP {response.status_code}: {response.text[:200]}"
            )
        content_type = response.headers.get("content-type", "audio/mpeg")
        if "audio" not in content_type:
            content_type = "audio/mpeg"
        return response.content, content_type

