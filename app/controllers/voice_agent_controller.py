"""
Voice Agent Controller - API endpoints for voice agent management
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional, List
from app.schemas.voice_agent import (
    VoiceAgentRequestResponse,
    VoiceAgentResponse,
    VoiceAgentUpdateRequest,
    VoiceAgentStatusUpdateRequest,
    VoiceAgentRequestListResponse,
    VoiceAgentListResponse
)
from app.services.voice_agent_service import (
    request_voice_agent,
    get_voice_agent_request,
    approve_voice_agent_request,
    reject_voice_agent_request,
    get_voice_agent,
    update_voice_agent,
    toggle_voice_agent_status,
    get_all_voice_agent_requests,
    get_all_voice_agents
)
from app.utils.dependencies import get_current_real_estate_agent_id, get_current_admin_id
from pydantic import BaseModel, Field

router = APIRouter(prefix="/agent/voice-agent", tags=["Voice Agent"])

DEFAULT_PREVIEW_TEXT = (
    "Hi, I'm calling on behalf of your real estate agent about a property you listed. "
    "Do you have a moment to chat?"
)


# Agent Endpoints
@router.post("/request", response_model=VoiceAgentRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_voice_agent_endpoint(
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Agent requests a voice agent"""
    try:
        request = await request_voice_agent(agent_id)
        return VoiceAgentRequestResponse(**request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=VoiceAgentResponse)
async def get_voice_agent_endpoint(
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get agent's voice agent configuration"""
    voice_agent = await get_voice_agent(agent_id)
    if not voice_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice agent not found. Please request one first."
        )
    return VoiceAgentResponse(**voice_agent)


@router.get("/status", response_model=VoiceAgentRequestResponse)
async def get_voice_agent_status_endpoint(
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get voice agent request status"""
    request = await get_voice_agent_request(agent_id)
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No voice agent request found"
        )
    return VoiceAgentRequestResponse(**request)


@router.patch("", response_model=VoiceAgentResponse)
async def update_voice_agent_endpoint(
    update_data: VoiceAgentUpdateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Update voice agent configuration"""
    try:
        update_dict = update_data.dict(exclude_unset=True)
        voice_agent = await update_voice_agent(agent_id, update_dict)
        return VoiceAgentResponse(**voice_agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/toggle-status", response_model=VoiceAgentResponse)
async def toggle_voice_agent_status_endpoint(
    status_data: VoiceAgentStatusUpdateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Toggle voice agent status (active/inactive)"""
    try:
        result = await toggle_voice_agent_status(agent_id, status_data.status)
        voice_agent = await get_voice_agent(agent_id)
        return VoiceAgentResponse(**voice_agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ── ElevenLabs Voice Preview ──

class VoicePreviewRequest(BaseModel):
    voice_id: str
    text: Optional[str] = Field(default=None, max_length=500)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity_boost: float = Field(default=0.75, ge=0.0, le=1.0)


@router.post("/voice/preview")
async def preview_voice(
    body: VoicePreviewRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    """
    Generate a short TTS sample for browser preview.
    Returns a token URL the frontend can use in an <audio> element.
    """
    from app.services.elevenlabs_tts_service import (
        synthesize_speech,
        is_enabled,
        get_tts_cache_ttl_seconds,
    )
    from app.config import settings as app_settings

    if not is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ElevenLabs is not configured. Add ELEVENLABS_API_KEY to server settings.",
        )

    sample_text = body.text or DEFAULT_PREVIEW_TEXT
    tts = await synthesize_speech(
        text=sample_text,
        voice_id=body.voice_id,
        speed=body.speed,
        stability=body.stability,
        similarity_boost=body.similarity_boost,
    )
    if not tts.token:
        msg = tts.error_message or "Failed to generate voice preview."
        # ElevenLabs free tier: library voices often return 402 paid_plan_required
        if tts.error_http_status == 402:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=msg,
        )

    base_url = app_settings.TWILIO_VOICE_WEBHOOK_URL or ""
    preview_url = f"{base_url}/tts/preview/{tts.token}" if base_url else f"/tts/preview/{tts.token}"

    return {
        "preview_url": preview_url,
        "token": tts.token,
        "expires_in": get_tts_cache_ttl_seconds(),
    }


@router.get("/voice/status")
async def voice_tts_status(
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    """Check if ElevenLabs TTS is configured and available."""
    from app.services.elevenlabs_tts_service import is_enabled
    return {"enabled": is_enabled()}

