"""
Twilio Webhook Controller - Public endpoints for Twilio webhooks
No authentication required (Twilio validates requests)
"""
from fastapi import APIRouter, Request
from fastapi.responses import Response
from app.services.twilio_service.webhook_service import (
    handle_voice_webhook,
    handle_status_webhook,
    handle_recording_webhook
)

router = APIRouter(prefix="/webhooks/twilio", tags=["Webhooks"])


@router.post("/voice", response_class=Response)
async def twilio_voice_webhook(request: Request):
    """
    Handle incoming voice webhook from Twilio
    Returns TwiML XML response
    """
    try:
        # Get form data from Twilio
        form_data = await request.form()
        form_dict = dict(form_data)
        
        # Process webhook
        twiml_response = await handle_voice_webhook(form_dict)
        
        # Return TwiML XML
        return Response(
            content=twiml_response,
            media_type="application/xml"
        )
    except Exception as e:
        # Return error TwiML
        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say("Sorry, an error occurred. Please try again later.", voice="alice")
        response.hangup()
        return Response(
            content=str(response),
            media_type="application/xml"
        )


@router.post("/status")
async def twilio_status_webhook(request: Request):
    """
    Handle call status updates from Twilio
    """
    try:
        form_data = await request.form()
        form_dict = dict(form_data)
        await handle_status_webhook(form_dict)
        return {"status": "ok"}
    except Exception as e:
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

