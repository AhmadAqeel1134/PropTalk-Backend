from typing import Optional, List
from datetime import datetime
import uuid
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.phone_number import PhoneNumber
from app.services.twilio_service import purchase_phone_number, release_phone_number


async def assign_phone_number_to_agent(real_estate_agent_id: str, area_code: Optional[str] = None) -> dict:
    """Assign a new phone number to a real estate agent"""
    async with AsyncSessionLocal() as session:
        # Check if agent already has an active phone number
        stmt = select(PhoneNumber).where(
            PhoneNumber.real_estate_agent_id == real_estate_agent_id,
            PhoneNumber.is_active == True
        )
        result = await session.execute(stmt)
        existing_phone = result.scalar_one_or_none()
        
        if existing_phone:
            raise ValueError("Agent already has an active phone number")
        
        # Purchase phone number from Twilio
        twilio_data = await purchase_phone_number(area_code)
        
        # Create phone number record
        phone_id = str(uuid.uuid4())
        new_phone = PhoneNumber(
            id=phone_id,
            real_estate_agent_id=real_estate_agent_id,
            twilio_phone_number=twilio_data["phone_number"],
            twilio_sid=twilio_data["sid"],
            is_active=True,
        )
        
        session.add(new_phone)
        await session.commit()
        await session.refresh(new_phone)
        
        return {
            "id": phone_id,
            "real_estate_agent_id": real_estate_agent_id,
            "twilio_phone_number": twilio_data["phone_number"],
            "twilio_sid": twilio_data["sid"],
            "is_active": True,
            "created_at": new_phone.created_at.isoformat() if new_phone.created_at else "",
            "updated_at": new_phone.updated_at.isoformat() if new_phone.updated_at else "",
        }


async def get_phone_number_by_agent_id(real_estate_agent_id: str) -> Optional[dict]:
    """Get phone number for a real estate agent"""
    async with AsyncSessionLocal() as session:
        stmt = select(PhoneNumber).where(
            PhoneNumber.real_estate_agent_id == real_estate_agent_id,
            PhoneNumber.is_active == True
        )
        result = await session.execute(stmt)
        phone = result.scalar_one_or_none()
        
        if not phone:
            return None
        
        return {
            "id": phone.id,
            "real_estate_agent_id": phone.real_estate_agent_id,
            "twilio_phone_number": phone.twilio_phone_number,
            "twilio_sid": phone.twilio_sid,
            "is_active": phone.is_active,
            "created_at": phone.created_at.isoformat() if phone.created_at else "",
            "updated_at": phone.updated_at.isoformat() if phone.updated_at else "",
        }


async def get_phone_number_by_id(phone_id: str) -> Optional[dict]:
    """Get phone number by ID"""
    async with AsyncSessionLocal() as session:
        stmt = select(PhoneNumber).where(PhoneNumber.id == phone_id)
        result = await session.execute(stmt)
        phone = result.scalar_one_or_none()
        
        if not phone:
            return None
        
        return {
            "id": phone.id,
            "real_estate_agent_id": phone.real_estate_agent_id,
            "twilio_phone_number": phone.twilio_phone_number,
            "twilio_sid": phone.twilio_sid,
            "is_active": phone.is_active,
            "created_at": phone.created_at.isoformat() if phone.created_at else "",
            "updated_at": phone.updated_at.isoformat() if phone.updated_at else "",
        }


async def update_phone_number(phone_id: str, update_data: dict) -> Optional[dict]:
    """Update phone number"""
    async with AsyncSessionLocal() as session:
        # Check if phone exists
        stmt = select(PhoneNumber).where(PhoneNumber.id == phone_id)
        result = await session.execute(stmt)
        phone = result.scalar_one_or_none()
        
        if not phone:
            return None
        
        # If deactivating, release from Twilio
        if "is_active" in update_data and update_data["is_active"] is False:
            await release_phone_number(phone.twilio_sid)
        
        # Update fields
        for key, value in update_data.items():
            if value is not None:
                setattr(phone, key, value)
        
        await session.commit()
        await session.refresh(phone)
        
        # Return updated phone number
        return {
            "id": phone.id,
            "real_estate_agent_id": phone.real_estate_agent_id,
            "twilio_phone_number": phone.twilio_phone_number,
            "twilio_sid": phone.twilio_sid,
            "is_active": phone.is_active,
            "created_at": phone.created_at.isoformat() if phone.created_at else "",
            "updated_at": phone.updated_at.isoformat() if phone.updated_at else "",
        }


async def get_all_phone_numbers() -> List[dict]:
    """Get all phone numbers"""
    async with AsyncSessionLocal() as session:
        stmt = select(PhoneNumber)
        result = await session.execute(stmt)
        phones = result.scalars().all()
        
        return [
            {
                "id": phone.id,
                "real_estate_agent_id": phone.real_estate_agent_id,
                "twilio_phone_number": phone.twilio_phone_number,
                "twilio_sid": phone.twilio_sid,
                "is_active": phone.is_active,
                "created_at": phone.created_at.isoformat() if phone.created_at else "",
                "updated_at": phone.updated_at.isoformat() if phone.updated_at else "",
            }
            for phone in phones
        ]
