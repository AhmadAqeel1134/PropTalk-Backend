"""
Twilio Client Service - Twilio client management and phone number operations
Low-level Twilio API interactions
"""
from twilio.rest import Client
from app.config import settings
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

twilio_client: Optional[Client] = None


def get_twilio_client() -> Client:
    """Get or create Twilio client singleton"""
    global twilio_client
    if twilio_client is None:
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            raise ValueError("Twilio credentials not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env")
        twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    return twilio_client


def purchase_phone_number_sync(area_code: Optional[str] = None) -> Dict[str, str]:
    """
    Purchase a phone number from Twilio (synchronous)
    Returns: {"phone_number": "+1234567890", "sid": "PN..."}
    """
    try:
        client = get_twilio_client()
        
        if area_code:
            available_numbers = client.available_phone_numbers('US').local.list(area_code=area_code, limit=1)
        else:
            available_numbers = client.available_phone_numbers('US').local.list(limit=1)
        
        if not available_numbers:
            raise ValueError("No available phone numbers found")
        
        phone_number = available_numbers[0].phone_number
        purchased_number = client.incoming_phone_numbers.create(phone_number=phone_number)
        
        return {
            "phone_number": purchased_number.phone_number,
            "sid": purchased_number.sid
        }
    except Exception as e:
        logger.error(f"Error purchasing phone number: {str(e)}")
        raise ValueError(f"Failed to purchase phone number: {str(e)}")


async def purchase_phone_number(area_code: Optional[str] = None) -> Dict[str, str]:
    """Async wrapper for purchasing phone number"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, purchase_phone_number_sync, area_code)


def get_existing_phone_number_sync(phone_number: str) -> Dict[str, str]:
    """
    Look up an existing Twilio incoming phone number by phone number.
    Returns: {"phone_number": "+1234567890", "sid": "PN..."}
    """
    try:
        client = get_twilio_client()
        # Twilio normalizes phone numbers to E.164, so we rely on exact match
        incoming_numbers = client.incoming_phone_numbers.list(phone_number=phone_number, limit=1)
        if not incoming_numbers:
            raise ValueError("Phone number not found in Twilio account")

        number = incoming_numbers[0]
        return {
            "phone_number": number.phone_number,
            "sid": number.sid,
        }
    except Exception as e:
        logger.error(f"Error looking up existing phone number: {str(e)}")
        raise ValueError(f"Failed to find existing phone number: {str(e)}")


async def get_existing_phone_number(phone_number: str) -> Dict[str, str]:
    """Async wrapper for looking up an existing Twilio phone number"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_existing_phone_number_sync, phone_number)


def release_phone_number_sync(twilio_sid: str) -> bool:
    """Release a phone number from Twilio (synchronous)"""
    try:
        client = get_twilio_client()
        client.incoming_phone_numbers(twilio_sid).delete()
        return True
    except Exception as e:
        logger.error(f"Error releasing phone number: {str(e)}")
        return False


async def release_phone_number(twilio_sid: str) -> bool:
    """Async wrapper for releasing phone number"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, release_phone_number_sync, twilio_sid)

