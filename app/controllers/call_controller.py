"""
Call Controller - API endpoints for call management
"""
import logging
import httpx
import base64
from fastapi import APIRouter, HTTPException, Depends, status, Query, Request, Response
from typing import Optional, List, Dict
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
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent/calls", tags=["Calls"])


# Agent call statistics (day/week/month) - placed before call_id routes to avoid path conflicts
@router.get("/stats", response_model=CallStatisticsResponse)
async def get_agent_call_statistics(
    period: str = Query("week", pattern="^(day|week|month)$"),
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get call statistics for the current agent (day/week/month)"""
    try:
        stats = await get_call_statistics(agent_id, period)
        return CallStatisticsResponse(**stats)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


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
    direction: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get paginated call history with server-side filtering and search"""
    calls, total = await get_calls_by_agent(
        real_estate_agent_id=agent_id,
        page=page,
        page_size=page_size,
        status=status,
        direction=direction,
        search=search
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
    """Get call recording metadata"""
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
    # Return proxied URL instead of direct Twilio URL
    proxied_url = f"/agent/calls/{call_id}/recording/stream"
    return CallRecordingResponse(
        recording_url=proxied_url,
        recording_sid=call.get("recording_sid", ""),
        duration_seconds=call.get("duration_seconds", 0)
    )


@router.get("/{call_id}/recording/stream")
async def stream_call_recording(
    call_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Stream call recording from Twilio with authentication (proxied)"""
    # Verify call belongs to agent
    call = await get_call_by_id(call_id, agent_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    recording_url = call.get("recording_url")
    if not recording_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not available"
        )
    
    # Check Twilio credentials
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio credentials not configured"
        )
    
    # Create Basic Auth header for Twilio
    credentials = f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded_credentials}"
    
    try:
        # Twilio recording URLs might need .mp3 extension for proper format
        # If URL doesn't end with .mp3 or .wav, try adding .mp3
        twilio_url = recording_url
        if not twilio_url.endswith(('.mp3', '.wav', '.m4a')):
            # Check if it's a Twilio API URL and append .mp3
            if 'api.twilio.com' in twilio_url and '/Recordings/' in twilio_url:
                twilio_url = f"{recording_url}.mp3"
        
        # Fetch recording from Twilio with authentication
        async with httpx.AsyncClient() as client:
            response = await client.get(
                twilio_url,
                headers={
                    "Authorization": auth_header,
                    "Accept": "audio/mpeg, audio/mp3, */*"
                },
                timeout=30.0,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch recording from Twilio: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch recording from Twilio"
                )
            
            # Determine content type from response
            content_type = response.headers.get("content-type", "audio/mpeg")
            if "audio" not in content_type:
                content_type = "audio/mpeg"
            
            # Stream the response
            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="recording_{call_id}.mp3"',
                    "Cache-Control": "public, max-age=3600",
                    "Accept-Ranges": "bytes"
                }
            )
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching recording from Twilio for call {call_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout fetching recording"
        )
    except Exception as e:
        logger.error(f"Error streaming recording: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error streaming recording: {str(e)}"
        )


@router.get("/stats", response_model=CallStatisticsResponse)
async def get_agent_call_statistics(
    period: str = Query("week", pattern="^(day|week|month)$"),
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get call statistics for the current agent (day/week/month)"""
    try:
        stats = await get_call_statistics(agent_id, period)
        return CallStatisticsResponse(**stats)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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


@router.get("/{call_id}/conversation-history")
async def get_conversation_history_endpoint(
    call_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get structured conversation history for a call"""
    call = await get_call_by_id(call_id, agent_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    twilio_call_sid = call.get("twilio_call_sid")
    if not twilio_call_sid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call SID not found"
        )
    
    # Try to get conversation history from memory
    from app.services.conversation.state_manager import get_conversation_history
    history = get_conversation_history(twilio_call_sid)
    
    if history:
        # Return structured history
        return {
            "history": history,
            "source": "memory"
        }
    
    # If we have a stored structured transcript, return it
    transcript_json = call.get("transcript_json")
    if transcript_json:
        return {
            "history": transcript_json,
            "source": "stored"
        }
    
    # If no structured history, try to parse transcript
    transcript = call.get("transcript")
    if transcript:
        # Parse transcript into messages (simple heuristic)
        parsed_messages = _parse_transcript_to_messages(transcript, call.get("direction", "outbound"))
        return {
            "history": parsed_messages,
            "source": "parsed"
        }
    
    return {
        "history": [],
        "source": "none"
    }


def _parse_transcript_to_messages(transcript: str, direction: str) -> List[Dict]:
    """
    Parse plain text transcript into structured messages
    This is a heuristic approach - assumes alternating user/agent messages
    """
    import re
    messages = []
    
    # Split by common patterns (periods, question marks, newlines)
    # This is a simple heuristic - can be improved
    sentences = re.split(r'[.!?]\s+|\n+', transcript.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Alternate between user and agent
    # For outbound: agent speaks first, then user, then agent...
    # For inbound: user might speak first, then agent...
    is_agent_turn = direction == "outbound"  # Outbound calls start with agent greeting
    
    for i, sentence in enumerate(sentences):
        if not sentence:
            continue
        
        # Skip very short sentences (likely artifacts)
        if len(sentence) < 3:
            continue
        
        role = "assistant" if is_agent_turn else "user"
        messages.append({
            "role": role,
            "content": sentence,
            "timestamp": None  # We don't have timestamps from plain text
        })
        
        is_agent_turn = not is_agent_turn
    
    return messages



