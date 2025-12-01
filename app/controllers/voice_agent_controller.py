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
from pydantic import BaseModel

router = APIRouter(prefix="/agent/voice-agent", tags=["Voice Agent"])


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



