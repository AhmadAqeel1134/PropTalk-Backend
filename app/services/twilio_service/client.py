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
        if not client:
            raise ValueError("Twilio client not configured. Please check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env")
        
        # Normalize phone number to E.164 format if needed
        normalized = phone_number.strip()
        if not normalized.startswith("+"):
            # Try to add + if it looks like a number
            if normalized.replace(" ", "").replace("-", "").isdigit():
                normalized = "+" + normalized.replace(" ", "").replace("-", "")
        
        # Twilio normalizes phone numbers to E.164, so we rely on exact match
        incoming_numbers = client.incoming_phone_numbers.list(phone_number=normalized, limit=1)
        if not incoming_numbers:
            # Try without + prefix
            if normalized.startswith("+"):
                incoming_numbers = client.incoming_phone_numbers.list(phone_number=normalized[1:], limit=1)
        
        if not incoming_numbers:
            raise ValueError(f"Phone number '{phone_number}' not found in your Twilio account. Please ensure the number is purchased in Twilio Console or leave phone number empty to auto-purchase a new number.")

        number = incoming_numbers[0]
        return {
            "phone_number": number.phone_number,
            "sid": number.sid,
        }
    except ValueError:
        # Re-raise ValueError as-is (already has good message)
        raise
    except Exception as e:
        logger.error(f"Error looking up existing phone number: {str(e)}")
        raise ValueError(f"Failed to find existing phone number '{phone_number}': {str(e)}. Please check Twilio credentials and ensure the number exists in your Twilio account.")


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


def update_phone_number_webhooks_sync(twilio_sid: str) -> bool:
    """
    Update phone number webhook URLs in Twilio to match current TWILIO_VOICE_WEBHOOK_URL
    This ensures status callbacks use the correct URL
    """
    try:
        client = get_twilio_client()
        if not settings.TWILIO_VOICE_WEBHOOK_URL:
            logger.warning("TWILIO_VOICE_WEBHOOK_URL not configured, skipping webhook update")
            return False
        
        base_url = settings.TWILIO_VOICE_WEBHOOK_URL.rstrip('/')
        voice_url = f"{base_url}/webhooks/twilio/voice"
        status_callback = f"{base_url}/webhooks/twilio/status"
        
        logger.info(f"Updating phone number {twilio_sid} webhooks to: {base_url}")
        
        client.incoming_phone_numbers(twilio_sid).update(
            voice_url=voice_url,
            voice_method='POST',
            status_callback=status_callback,
            status_callback_method='POST',
            voice_fallback_url=voice_url,
            voice_fallback_method='POST'
        )
        
        logger.info(f"✅ Successfully updated phone number {twilio_sid} webhooks")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating phone number webhooks: {str(e)}", exc_info=True)
        return False


async def update_phone_number_webhooks(twilio_sid: str) -> bool:
    """Async wrapper for updating phone number webhooks"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, update_phone_number_webhooks_sync, twilio_sid)

