"""
Call Controller - API endpoints for call management
"""
from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import Optional
from app.schemas.call import (
    CallResponse,
    PaginatedCallsResponse,
    CallInitiateRequest,
    CallBatchRequest,
    CallRecordingResponse,
    CallTranscriptResponse,
    CallStatisticsResponse
)
from app.services.call_service import (
    initiate_call,
    initiate_batch_calls,
    get_calls_by_agent,
    get_call_by_id
)
from app.services.call_statistics_service import get_call_statistics
from app.utils.dependencies import get_current_real_estate_agent_id, get_current_admin_id

router = APIRouter(prefix="/agent/calls", tags=["Calls"])


# Agent Endpoints
@router.post("/initiate", response_model=dict, status_code=status.HTTP_201_CREATED)
async def initiate_call_endpoint(
    request: CallInitiateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Initiate an outbound call"""
    try:
        result = await initiate_call(
            real_estate_agent_id=agent_id,
            contact_id=request.contact_id,
            phone_number=request.phone_number
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/batch", response_model=dict, status_code=status.HTTP_201_CREATED)
async def initiate_batch_calls_endpoint(
    request: CallBatchRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Initiate batch calls"""
    try:
        result = await initiate_batch_calls(
            real_estate_agent_id=agent_id,
            contact_ids=request.contact_ids,
            delay_seconds=request.delay_seconds
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=PaginatedCallsResponse)
async def get_calls_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get paginated call history"""
    calls, total = await get_calls_by_agent(
        real_estate_agent_id=agent_id,
        page=page,
        page_size=page_size,
        status=status
    )
    return PaginatedCallsResponse(
        items=[CallResponse(**call) for call in calls],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{call_id}", response_model=CallResponse)
async def get_call_endpoint(
    call_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get specific call details"""
    call = await get_call_by_id(call_id, agent_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    return CallResponse(**call)


@router.get("/{call_id}/recording", response_model=CallRecordingResponse)
async def get_call_recording_endpoint(
    call_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get call recording URL"""
    call = await get_call_by_id(call_id, agent_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    if not call.get("recording_url"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not available"
        )
    return CallRecordingResponse(
        recording_url=call["recording_url"],
        recording_sid=call.get("recording_sid", ""),
        duration_seconds=call.get("duration_seconds", 0)
    )


@router.get("/{call_id}/transcript", response_model=CallTranscriptResponse)
async def get_call_transcript_endpoint(
    call_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get call transcript"""
    call = await get_call_by_id(call_id, agent_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    if not call.get("transcript"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not available"
        )
    return CallTranscriptResponse(transcript=call["transcript"])



