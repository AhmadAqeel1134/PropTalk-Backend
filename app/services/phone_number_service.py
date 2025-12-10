from typing import Optional, List
from datetime import datetime
import uuid
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.phone_number import PhoneNumber
from app.services.twilio_service.client import (
    purchase_phone_number,
    release_phone_number,
    get_existing_phone_number,
)


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


async def assign_existing_phone_number_to_agent(real_estate_agent_id: str, phone_number: str) -> dict:
    """
    Assign an existing Twilio phone number (already purchased in the Twilio console)
    to a real estate agent.
    
    Admin manually purchases number in Twilio dashboard and enters it here.
    No validation against Twilio account - just accepts the number and creates record.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📞 [PHONE_ASSIGN] Starting phone number assignment")
    logger.info(f"📞 [PHONE_ASSIGN] agent_id={real_estate_agent_id}, phone_number='{phone_number}' (type: {type(phone_number)})")
    
    async with AsyncSessionLocal() as session:
        # Check if agent already has an active phone number
        logger.info(f"📞 [PHONE_ASSIGN] Step 1: Checking for existing active phone number...")
        stmt = select(PhoneNumber).where(
            PhoneNumber.real_estate_agent_id == real_estate_agent_id,
            PhoneNumber.is_active == True,
        )
        result = await session.execute(stmt)
        existing_phone = result.scalar_one_or_none()

        if existing_phone:
            logger.error(f"❌ [PHONE_ASSIGN] Agent already has an active phone number: {existing_phone.twilio_phone_number}")
            raise ValueError("Agent already has an active phone number")

        logger.info(f"📞 [PHONE_ASSIGN] No existing active phone number found")

        # Normalize phone number (ensure E.164 format) - do this FIRST
        logger.info(f"📞 [PHONE_ASSIGN] Step 2: Normalizing phone number...")
        logger.info(f"📞 [PHONE_ASSIGN] Original input: '{phone_number}'")
        
        # Remove all spaces, dashes, parentheses, dots, and other formatting characters
        cleaned = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "").strip()
        logger.info(f"📞 [PHONE_ASSIGN] After removing formatting: '{cleaned}'")
        
        # Ensure it starts with +
        if not cleaned.startswith("+"):
            # If it's all digits, add +
            if cleaned.isdigit():
                normalized_number = "+" + cleaned
                logger.info(f"📞 [PHONE_ASSIGN] Added + prefix: '{normalized_number}'")
            else:
                # If it has non-digit characters, try to extract digits
                digits_only = ''.join(filter(str.isdigit, cleaned))
                if digits_only:
                    normalized_number = "+" + digits_only
                    logger.info(f"📞 [PHONE_ASSIGN] Extracted digits and added +: '{normalized_number}'")
                else:
                    normalized_number = cleaned
                    logger.warning(f"⚠️ [PHONE_ASSIGN] Could not extract valid digits from: '{phone_number}'")
        else:
            # Already has +, just use it
            normalized_number = cleaned
            logger.info(f"📞 [PHONE_ASSIGN] Already has + prefix: '{normalized_number}'")

        logger.info(f"📞 [PHONE_ASSIGN] Final normalized number: '{normalized_number}'")
        
        # Ensure this phone number is not already assigned (check normalized version)
        logger.info(f"📞 [PHONE_ASSIGN] Step 3: Checking if phone number is already assigned to another agent...")
        number_stmt = select(PhoneNumber).where(PhoneNumber.twilio_phone_number == normalized_number)
        number_result = await session.execute(number_stmt)
        existing_number = number_result.scalar_one_or_none()
        if existing_number:
            logger.error(f"❌ [PHONE_ASSIGN] Phone number already assigned to agent: {existing_number.real_estate_agent_id}")
            raise ValueError("This phone number is already assigned to an agent")

        logger.info(f"📞 [PHONE_ASSIGN] Phone number is available")

        # Try to look up SID from Twilio (optional - don't fail if it doesn't work)
        logger.info(f"📞 [PHONE_ASSIGN] Step 4: Attempting Twilio SID lookup (optional)...")
        twilio_sid = None
        try:
            twilio_data = await get_existing_phone_number(normalized_number)
            twilio_sid = twilio_data["sid"]
            normalized_number = twilio_data["phone_number"]  # Use Twilio's normalized format
            logger.info(f"✅ [PHONE_ASSIGN] Found Twilio SID for {normalized_number}: {twilio_sid}")
        except Exception as e:
            # If lookup fails, use placeholder SID - admin can update it later if needed
            # Format: MANUAL-{timestamp}-{last4digits}
            import time
            last_digits = normalized_number.replace("+", "").replace(" ", "").replace("-", "")[-4:]
            twilio_sid = f"MANUAL-{int(time.time())}-{last_digits}"
            logger.warning(f"⚠️ [PHONE_ASSIGN] Could not find phone number in Twilio account: {str(e)}. Using placeholder SID: {twilio_sid}")

        logger.info(f"📞 [PHONE_ASSIGN] Step 5: Creating phone number record...")
        logger.info(f"📞 [PHONE_ASSIGN] twilio_phone_number='{normalized_number}', twilio_sid='{twilio_sid}'")

        phone_id = str(uuid.uuid4())
        new_phone = PhoneNumber(
            id=phone_id,
            real_estate_agent_id=real_estate_agent_id,
            twilio_phone_number=normalized_number,
            twilio_sid=twilio_sid,
            is_active=True,
        )

        logger.info(f"📞 [PHONE_ASSIGN] Step 6: Saving to database...")
        session.add(new_phone)
        await session.commit()
        await session.refresh(new_phone)

        # Update webhook URLs in Twilio to match current TWILIO_VOICE_WEBHOOK_URL
        # This ensures status callbacks use the correct URL (fixes old tunnel URL issues)
        if twilio_sid and not twilio_sid.startswith("MANUAL-"):
            try:
                from app.services.twilio_service.client import update_phone_number_webhooks
                logger.info(f"📞 [PHONE_ASSIGN] Step 7: Updating Twilio webhook URLs...")
                webhook_updated = await update_phone_number_webhooks(twilio_sid)
                if webhook_updated:
                    logger.info(f"✅ [PHONE_ASSIGN] Twilio webhook URLs updated successfully")
                else:
                    logger.warning(f"⚠️ [PHONE_ASSIGN] Failed to update Twilio webhook URLs (non-critical)")
            except Exception as e:
                logger.warning(f"⚠️ [PHONE_ASSIGN] Error updating Twilio webhooks: {str(e)} (non-critical)")

        logger.info(f"✅ [PHONE_ASSIGN] Phone number assigned successfully: id={phone_id}, number={normalized_number}")
        return {
            "id": phone_id,
            "real_estate_agent_id": real_estate_agent_id,
            "twilio_phone_number": new_phone.twilio_phone_number,
            "twilio_sid": new_phone.twilio_sid,
            "is_active": new_phone.is_active,
            "created_at": new_phone.created_at.isoformat() if new_phone.created_at else "",
            "updated_at": new_phone.updated_at.isoformat() if new_phone.updated_at else "",
        }
