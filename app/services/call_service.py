"""
Call Service - Business logic for call management
Handles call initiation, recording, and history
"""
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import uuid
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
from app.database.connection import AsyncSessionLocal
from app.models.call import Call
from app.models.voice_agent import VoiceAgent
from app.models.contact import Contact
from app.services.twilio_service.client import get_twilio_client
from app.config import settings


async def initiate_call(
    real_estate_agent_id: str,
    contact_id: Optional[str],
    phone_number: str
) -> Dict:
    """Initiate an outbound call via Twilio"""
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
            raise ValueError("Active voice agent not found")
        
        if not voice_agent.phone_number:
            raise ValueError("Voice agent does not have a phone number assigned")
        
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
        
        # Normalize phone number (ensure E.164 format)
        if not phone_number.startswith("+"):
            phone_number = "+" + phone_number.lstrip("+")
        
        # Create call record
        call_id = str(uuid.uuid4())
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
        
        # Make call via Twilio
        try:
            client = get_twilio_client()
            # Get webhook URL from settings
            base_url = settings.TWILIO_VOICE_WEBHOOK_URL
            if not base_url:
                raise ValueError("TWILIO_VOICE_WEBHOOK_URL not configured in environment")
            
            voice_url = f"{base_url}/webhooks/twilio/voice"
            
            recording_callback = f"{base_url}/webhooks/twilio/recording"
            
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
            
            # Update call with Twilio SID
            new_call.twilio_call_sid = call.sid
            await session.commit()
            await session.refresh(new_call)
            
            return {
                "id": new_call.id,
                "twilio_call_sid": call.sid,
                "status": "initiated",
                "to_number": phone_number,
                "from_number": voice_agent.phone_number.twilio_phone_number,
            }
        except Exception as e:
            # Update call status to failed
            new_call.status = "failed"
            await session.commit()
            raise ValueError(f"Failed to initiate call: {str(e)}")


async def initiate_batch_calls(
    real_estate_agent_id: str,
    contact_ids: List[str],
    delay_seconds: int = 30
) -> Dict:
    """Initiate batch calls with delay between each"""
    calls = []
    errors = []
    
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
                if i < len(contact_ids) - 1:
                    import asyncio
                    await asyncio.sleep(delay_seconds)
        except Exception as e:
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
    status: Optional[str] = None
) -> Tuple[List[Dict], int]:
    """Get paginated calls for an agent"""
    async with AsyncSessionLocal() as session:
        # Build query
        conditions = [Call.real_estate_agent_id == real_estate_agent_id]
        if status:
            conditions.append(Call.status == status)
        
        where_clause = and_(*conditions)
        
        # Total count
        count_stmt = select(func.count()).select_from(Call).where(where_clause)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one() or 0
        
        # Paginated query
        stmt = (
            select(Call)
            .options(selectinload(Call.contact))
            .where(where_clause)
            .order_by(desc(Call.created_at))
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
        
        result = await session.execute(stmt)
        calls = result.scalars().all()
        
        items = [
            {
                "id": call.id,
                "voice_agent_id": call.voice_agent_id,
                "real_estate_agent_id": call.real_estate_agent_id,
                "twilio_call_sid": call.twilio_call_sid,
                "contact_id": call.contact_id,
                "contact_name": call.contact.name if call.contact else None,
                "from_number": call.from_number,
                "to_number": call.to_number,
                "status": call.status,
                "direction": call.direction,
                "duration_seconds": call.duration_seconds,
                "recording_url": call.recording_url,
                "recording_sid": call.recording_sid,
                "transcript": call.transcript,
                "started_at": call.started_at.isoformat() if call.started_at else None,
                "answered_at": call.answered_at.isoformat() if call.answered_at else None,
                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                "created_at": call.created_at.isoformat() if call.created_at else "",
                "updated_at": call.updated_at.isoformat() if call.updated_at else "",
            }
            for call in calls
        ]
        
        return items, total


async def get_call_by_id(call_id: str, real_estate_agent_id: str) -> Optional[Dict]:
    """Get a specific call by ID"""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Call)
            .options(selectinload(Call.contact))
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
        
        return {
            "id": call.id,
            "voice_agent_id": call.voice_agent_id,
            "real_estate_agent_id": call.real_estate_agent_id,
            "twilio_call_sid": call.twilio_call_sid,
            "contact_id": call.contact_id,
            "contact_name": call.contact.name if call.contact else None,
            "from_number": call.from_number,
            "to_number": call.to_number,
            "status": call.status,
            "direction": call.direction,
            "duration_seconds": call.duration_seconds,
            "recording_url": call.recording_url,
            "recording_sid": call.recording_sid,
            "transcript": call.transcript,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "answered_at": call.answered_at.isoformat() if call.answered_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "created_at": call.created_at.isoformat() if call.created_at else "",
            "updated_at": call.updated_at.isoformat() if call.updated_at else "",
        }


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


async def save_transcript(call_id: str, transcript: str) -> Optional[Dict]:
    """Save transcript for a call"""
    async with AsyncSessionLocal() as session:
        stmt = select(Call).where(Call.id == call_id)
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            return None
        
        call.transcript = transcript
        await session.commit()
        
        return {
            "id": call.id,
            "transcript": call.transcript,
        }

