"""
Twilio Webhook Controller - Public endpoints for Twilio webhooks
No authentication required (Twilio validates requests)
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import Response
from app.services.twilio_service.webhook_service import (
    handle_voice_webhook,
    handle_status_webhook,
    handle_recording_webhook
)

# Set up logging for webhooks
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["Webhooks"])


@router.get("/test")
async def test_webhook():
    """
    Simple test endpoint to verify webhook routes are accessible
    """
    return {
        "status": "ok",
        "message": "Webhook endpoints are accessible",
        "endpoints": {
            "voice": "/webhooks/twilio/voice",
            "status": "/webhooks/twilio/status",
            "recording": "/webhooks/twilio/recording"
        }
    }


@router.get("/voice")
@router.head("/voice")
async def twilio_voice_webhook_get(request: Request):
    """
    Handle GET/HEAD requests from Twilio (validation/health checks)
    Twilio sends GET/HEAD requests to validate webhook URLs
    """
    logger.info("✅ Twilio voice webhook validation request (GET/HEAD)")
    print("✅ GET/HEAD request received for /webhooks/twilio/voice")
    # Return 200 OK for validation
    return Response(content="OK", media_type="text/plain", status_code=200)


@router.post("/voice", response_class=Response)
async def twilio_voice_webhook(request: Request):
    """
    Handle incoming voice webhook from Twilio
    Returns TwiML XML response
    IMPORTANT: Must respond within 3 seconds for Twilio
    """
    import asyncio
    import traceback
    
    # Log that we received a POST request
    logger.info("📥 POST request received for /webhooks/twilio/voice")
    print("\n" + "="*60)
    print("📥 POST REQUEST RECEIVED - /webhooks/twilio/voice")
    print("="*60)
    
    try:
        # Get form data from Twilio (this is fast)
        form_data = await request.form()
        form_dict = dict(form_data)
        
        # Log ALL form data for debugging
        logger.info(f"📋 Form data received: {form_dict}")
        print(f"📋 Form data: {form_dict}")
        
        # Extract key fields
        call_sid = form_dict.get("CallSid", "unknown")
        from_number = form_dict.get("From", "unknown")
        to_number = form_dict.get("To", "unknown")
        call_status = form_dict.get("CallStatus", "unknown")
        
        # Print to console for visibility (works even if logging not configured)
        print(f"\n{'='*60}")
        print(f"🔔 TWILIO VOICE WEBHOOK RECEIVED!")
        print(f"📞 Call SID: {call_sid}")
        print(f"📱 From: {from_number}")
        print(f"📞 To: {to_number}")
        print(f"📊 Call Status: {call_status}")
        print(f"{'='*60}\n")
        
        logger.info(f"🔔 Twilio voice webhook - CallSid: {call_sid}, From: {from_number}, To: {to_number}, Status: {call_status}")
        
        # Process webhook with timeout protection
        # Twilio expects response within 3 seconds, so we'll timeout after 2.5 seconds
        try:
            twiml_response = await asyncio.wait_for(
                handle_voice_webhook(form_dict),
                timeout=2.5
            )
            logger.info(f"✅ Returning TwiML response (length: {len(twiml_response)} bytes)")
            print(f"✅ TwiML response generated: {len(twiml_response)} bytes")
            print(f"📄 TwiML preview: {twiml_response[:200]}...")
        except asyncio.TimeoutError:
            logger.error("⏱️ Webhook processing timed out (>2.5s), returning fallback response")
            print("⏱️ TIMEOUT: Processing took too long, using fallback")
            # Return a simple fallback response
            from twilio.twiml.voice_response import VoiceResponse
            response = VoiceResponse()
            response.say("Hello, thank you for calling. Please hold.", voice="alice")
            # Use full URL if available, otherwise relative
            from app.config import settings
            webhook_url = f"{settings.TWILIO_VOICE_WEBHOOK_URL}/webhooks/twilio/voice" if settings.TWILIO_VOICE_WEBHOOK_URL else "/webhooks/twilio/voice"
            response.redirect(webhook_url, method="POST")
            twiml_response = str(response)
        
        # Return TwiML XML
        print(f"✅ Sending response to Twilio")
        return Response(
            content=twiml_response,
            media_type="application/xml",
            headers={
                "Cache-Control": "no-cache",
                "Content-Type": "application/xml; charset=utf-8"
            }
        )
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"❌ Error in voice webhook: {error_msg}", exc_info=True)
        print(f"\n❌ ERROR IN WEBHOOK HANDLER:")
        print(f"Error: {error_msg}")
        print(f"Traceback:\n{error_trace}\n")
        
        # Return error TwiML - always return something valid
        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say("Hello, thank you for calling. We're experiencing technical difficulties. Please try again later.", voice="alice")
        response.hangup()
        return Response(
            content=str(response),
            media_type="application/xml",
            headers={
                "Cache-Control": "no-cache",
                "Content-Type": "application/xml; charset=utf-8"
            }
        )


@router.get("/status")
@router.head("/status")
async def twilio_status_webhook_get(request: Request):
    """
    Handle GET/HEAD requests from Twilio (validation/health checks)
    Twilio sends GET/HEAD requests to validate webhook URLs
    """
    logger.info("✅ Twilio status webhook validation request (GET/HEAD)")
    print("✅ GET/HEAD request received for /webhooks/twilio/status")
    # Return 200 OK for validation
    return Response(content="OK", media_type="text/plain", status_code=200)


@router.post("/status")
async def twilio_status_webhook(request: Request):
    """
    Handle call status updates from Twilio
    """
    logger.info("📥 POST request received for /webhooks/twilio/status")
    print("📥 Status webhook POST received")
    
    try:
        form_data = await request.form()
        form_dict = dict(form_data)
        call_sid = form_dict.get("CallSid", "unknown")
        call_status = form_dict.get("CallStatus", "unknown")
        call_duration = form_dict.get("CallDuration", "0")
        
        logger.info(f"📊 Status webhook - CallSid: {call_sid}, Status: {call_status}, Duration: {call_duration}s")
        print(f"📊 Call Status Update - SID: {call_sid}, Status: {call_status}, Duration: {call_duration}s")
        
        # Process status update (non-blocking - don't fail if DB is down)
        try:
            await handle_status_webhook(form_dict)
            logger.info(f"✅ Status webhook processed successfully")
        except Exception as db_error:
            logger.warning(f"⚠️ Failed to update call status in DB: {db_error}")
            print(f"⚠️ DB update failed (non-critical): {db_error}")
            # Continue - status webhook is not critical for call to work
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error in status webhook: {str(e)}", exc_info=True)
        print(f"❌ Status webhook error: {str(e)}")
        # Log error but return 200 (Twilio expects 200)
        return {"status": "error", "message": str(e)}


@router.post("/recording")
async def twilio_recording_webhook(request: Request):
    """
    Handle recording status updates from Twilio
    """
    try:
        form_data = await request.form()
        form_dict = dict(form_data)
        await handle_recording_webhook(form_dict)
        return {"status": "ok"}
    except Exception as e:
        # Log error but return 200 (Twilio expects 200)
        return {"status": "error", "message": str(e)}

