"""
Call Controller - API endpoints for call management
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent/calls", tags=["Calls"])


# Agent Endpoints
@router.post("/initiate", response_model=dict, status_code=status.HTTP_201_CREATED)
async def initiate_call_endpoint(
    request: CallInitiateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id),
    http_request: Request = None
):
    """Initiate an outbound call"""
    # Log incoming request from frontend
    client_ip = http_request.client.host if http_request and http_request.client else "unknown"
    print("\n" + "="*70)
    print("📞 OUTBOUND CALL REQUEST RECEIVED FROM FRONTEND")
    print("="*70)
    print(f"👤 Agent ID: {agent_id}")
    print(f"📱 Phone Number: {request.phone_number}")
    print(f"📇 Contact ID: {request.contact_id or 'None'}")
    print(f"🌐 Client IP: {client_ip}")
    print(f"📋 Request Data: {request.model_dump()}")
    print("="*70 + "\n")
    
    logger.info(f"📞 Outbound call request - Agent: {agent_id}, Phone: {request.phone_number}, Contact: {request.contact_id}")
    
    try:
        print("🔄 Processing call initiation...")
        result = await initiate_call(
            real_estate_agent_id=agent_id,
            contact_id=request.contact_id,
            phone_number=request.phone_number
        )
        
        print("\n" + "="*70)
        print("✅ CALL INITIATED SUCCESSFULLY")
        print("="*70)
        print(f"📞 Call ID: {result.get('id', 'N/A')}")
        print(f"🔢 Twilio Call SID: {result.get('twilio_call_sid', 'N/A')}")
        print(f"📱 From: {result.get('from_number', 'N/A')}")
        print(f"📱 To: {result.get('to_number', 'N/A')}")
        print(f"📊 Status: {result.get('status', 'N/A')}")
        print("="*70 + "\n")
        
        logger.info(f"✅ Call initiated successfully - Call SID: {result.get('twilio_call_sid')}, To: {result.get('to_number')}")
        
        return result
    except ValueError as e:
        error_msg = str(e)
        print("\n" + "="*70)
        print("❌ CALL INITIATION FAILED")
        print("="*70)
        print(f"⚠️ Error: {error_msg}")
        print("="*70 + "\n")
        
        logger.error(f"❌ Call initiation failed - Agent: {agent_id}, Phone: {request.phone_number}, Error: {error_msg}")
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        error_msg = str(e)
        print("\n" + "="*70)
        print("❌ UNEXPECTED ERROR IN CALL INITIATION")
        print("="*70)
        print(f"⚠️ Error: {error_msg}")
        print(f"⚠️ Error Type: {type(e).__name__}")
        print("="*70 + "\n")
        
        logger.error(f"❌ Unexpected error in call initiation - Agent: {agent_id}, Error: {error_msg}", exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {error_msg}"
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



