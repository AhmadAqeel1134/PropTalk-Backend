"""
End-user portal: browse agents, then per-agent calls/showings scoped by JWT user + phone.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response

from app.schemas.auth import TokenResponse
from app.schemas.end_user import (
    EndUserRegisterRequest,
    EndUserLoginRequest,
    EndUserMeResponse,
    EndUserPhoneUpdateRequest,
    PublicAgentListItem,
    PublicAgentDetailResponse,
    UserChatRequest,
    UserChatResponse,
)
from app.schemas.call import (
    CallResponse,
    PaginatedCallsResponse,
    CallRecordingResponse,
    CallTranscriptResponse,
)
from app.schemas.showing import ShowingResponse, PaginatedShowingsResponse
from app.services.end_user_auth_service import (
    register_end_user,
    authenticate_end_user,
    get_end_user_by_id,
    update_end_user_phone,
)
from app.services.end_user_portal_service import list_public_agents, get_public_agent_detail
from app.services.call_service import (
    list_calls_for_agent_and_user_phone,
    get_call_by_id_for_agent_and_user_phone,
    fetch_twilio_recording_bytes,
)
from app.services.showing_service import (
    list_showings_for_agent_and_user_phone,
    get_showing_by_id_for_agent_and_user_phone,
)
from app.services.rag.rag_service import RagService, get_rag_service
from app.services.rag.telemetry_service import create_rag_query_log
from app.schemas.rag_metrics import RagQueryLogCreate
from app.utils.security import create_access_token
from app.utils.dependencies import get_current_end_user_id
import time

router = APIRouter(prefix="/user", tags=["End user portal"])


def _mask_call_recording_for_user(call: dict, agent_id: str) -> None:
    if call.get("recording_url"):
        call["recording_url"] = f"/user/agents/{agent_id}/calls/{call['id']}/recording/stream"


def _me_response(data: dict) -> EndUserMeResponse:
    return EndUserMeResponse(
        id=data["id"],
        email=data["email"],
        full_name=data["full_name"],
        phone_number=data.get("phone_number"),
        phone_saved_at=data.get("phone_saved_at"),
        is_active=data["is_active"],
        created_at=data.get("created_at") or "",
    )


async def _require_phone_digits(user_id: str) -> str:
    user = await get_end_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    raw = user.get("phone_number")
    digits = "".join(c for c in str(raw or "") if c.isdigit())
    if len(digits) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add your phone number (use My phone in the sidebar) to view your calls and showings with this agent.",
        )
    return digits


@router.post("/register", response_model=EndUserMeResponse, status_code=status.HTTP_201_CREATED)
async def register_end_user_endpoint(request: EndUserRegisterRequest):
    try:
        user = await register_end_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            phone_number=request.phone_number,
        )
        return _me_response(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login_end_user(request: EndUserLoginRequest):
    user = await authenticate_end_user(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token = create_access_token(
        data={"sub": user["id"], "email": user["email"], "type": "end_user"}
    )
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=EndUserMeResponse)
async def end_user_me(user_id: str = Depends(get_current_end_user_id)):
    user = await get_end_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _me_response(user)


@router.patch("/me/phone", response_model=EndUserMeResponse)
async def end_user_update_phone(
    request: EndUserPhoneUpdateRequest,
    user_id: str = Depends(get_current_end_user_id),
):
    try:
        user = await update_end_user_phone(user_id, request.phone_number)
        return _me_response(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/agents", response_model=List[PublicAgentListItem])
async def list_agents_directory(user_id: str = Depends(get_current_end_user_id)):
    _ = user_id
    items = await list_public_agents()
    return [PublicAgentListItem(**x) for x in items]


@router.get("/agents/{agent_id}", response_model=PublicAgentDetailResponse)
async def get_agent_directory_detail(
    agent_id: str,
    user_id: str = Depends(get_current_end_user_id),
):
    _ = user_id
    detail = await get_public_agent_detail(agent_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return PublicAgentDetailResponse(**detail)


@router.get("/agents/{agent_id}/calls", response_model=PaginatedCallsResponse)
async def list_user_calls_for_agent(
    agent_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_end_user_id),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    calls, total = await list_calls_for_agent_and_user_phone(
        real_estate_agent_id=agent_id,
        user_phone_digits=digits,
        page=page,
        page_size=page_size,
    )
    for c in calls:
        _mask_call_recording_for_user(c, agent_id)
    return PaginatedCallsResponse(
        items=[CallResponse(**c) for c in calls],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/agents/{agent_id}/calls/{call_id}", response_model=CallResponse)
async def get_user_call_for_agent(
    agent_id: str,
    call_id: str,
    user_id: str = Depends(get_current_end_user_id),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    call = await get_call_by_id_for_agent_and_user_phone(call_id, agent_id, digits)
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    _mask_call_recording_for_user(call, agent_id)
    return CallResponse(**call)


@router.get("/agents/{agent_id}/calls/{call_id}/recording", response_model=CallRecordingResponse)
async def get_user_call_recording_meta(
    agent_id: str,
    call_id: str,
    user_id: str = Depends(get_current_end_user_id),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    call = await get_call_by_id_for_agent_and_user_phone(call_id, agent_id, digits)
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    if not call.get("recording_url"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not available")
    proxied = f"/user/agents/{agent_id}/calls/{call_id}/recording/stream"
    return CallRecordingResponse(
        recording_url=proxied,
        recording_sid=call.get("recording_sid", ""),
        duration_seconds=call.get("duration_seconds", 0),
    )


@router.get("/agents/{agent_id}/calls/{call_id}/recording/stream")
async def stream_user_call_recording(
    agent_id: str,
    call_id: str,
    user_id: str = Depends(get_current_end_user_id),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    call = await get_call_by_id_for_agent_and_user_phone(call_id, agent_id, digits)
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    recording_url = call.get("recording_url")
    if not recording_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not available")
    try:
        content, content_type = await fetch_twilio_recording_bytes(recording_url)
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="recording_{call_id}.mp3"',
                "Cache-Control": "public, max-age=3600",
                "Accept-Ranges": "bytes",
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except RuntimeError as e:
        msg = str(e)
        if "401" in msg or "403" in msg:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Recording access denied by Twilio.",
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)


@router.get("/agents/{agent_id}/calls/{call_id}/transcript", response_model=CallTranscriptResponse)
async def get_user_call_transcript(
    agent_id: str,
    call_id: str,
    user_id: str = Depends(get_current_end_user_id),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    call = await get_call_by_id_for_agent_and_user_phone(call_id, agent_id, digits)
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    if not call.get("transcript"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not available")
    return CallTranscriptResponse(transcript=call["transcript"])


@router.get("/agents/{agent_id}/calls/{call_id}/conversation-history")
async def get_user_conversation_history(
    agent_id: str,
    call_id: str,
    user_id: str = Depends(get_current_end_user_id),
):
    from app.services.conversation.state_manager import get_conversation_history
    from app.utils.transcript_parse import parse_transcript_to_messages

    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    call = await get_call_by_id_for_agent_and_user_phone(call_id, agent_id, digits)
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    twilio_call_sid = call.get("twilio_call_sid")
    if twilio_call_sid:
        history = get_conversation_history(twilio_call_sid)
        if history:
            return {"history": history, "source": "memory"}

    transcript_json = call.get("transcript_json")
    if transcript_json:
        return {"history": transcript_json, "source": "stored"}

    transcript = call.get("transcript")
    if transcript:
        parsed = parse_transcript_to_messages(transcript, call.get("direction", "outbound"))
        return {"history": parsed, "source": "parsed"}

    return {"history": [], "source": "none"}


@router.get("/agents/{agent_id}/showings", response_model=PaginatedShowingsResponse)
async def list_user_showings_for_agent(
    agent_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_end_user_id),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    items, total = await list_showings_for_agent_and_user_phone(
        real_estate_agent_id=agent_id,
        user_phone_digits=digits,
        page=page,
        page_size=page_size,
    )
    return PaginatedShowingsResponse(
        items=[ShowingResponse(**s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/agents/{agent_id}/showings/{showing_id}", response_model=ShowingResponse)
async def get_user_showing_for_agent(
    agent_id: str,
    showing_id: str,
    user_id: str = Depends(get_current_end_user_id),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    s = await get_showing_by_id_for_agent_and_user_phone(showing_id, agent_id, digits)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Showing not found")
    return ShowingResponse(**s)


@router.post("/agents/{agent_id}/chat", response_model=UserChatResponse)
async def user_chat_with_agent_context(
    agent_id: str,
    body: UserChatRequest,
    user_id: str = Depends(get_current_end_user_id),
    rag: RagService = Depends(get_rag_service),
):
    if not await get_public_agent_detail(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    digits = await _require_phone_digits(user_id)
    started_at = time.perf_counter()
    status_value = "success"
    out = {}
    error_message = None
    try:
        out = await rag.answer_user_message(
            real_estate_agent_id=agent_id,
            end_user_id=user_id,
            end_user_phone_digits=digits,
            message=body.message,
        )
        return UserChatResponse(**out)
    except Exception as e:
        status_value = "error"
        error_message = str(e)
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        try:
            await create_rag_query_log(
                RagQueryLogCreate(
                    real_estate_agent_id=agent_id,
                    end_user_id=user_id,
                    question=body.message,
                    answer=out.get("answer"),
                    status=status_value,
                    error_message=error_message,
                    rag_enabled=bool(out.get("rag_enabled", False)),
                    retrieval_k=out.get("retrieval_k"),
                    retrieved_chunks=out.get("retrieved_chunks"),
                    context_recall_score=out.get("context_recall_score"),
                    context_precision_score=out.get("context_precision_score"),
                    answer_relevance_score=out.get("answer_relevance_score"),
                    faithfulness_score=out.get("faithfulness_score"),
                    correctness_score=out.get("correctness_score"),
                    citation_precision_score=out.get("citation_precision_score"),
                    hallucination_flag=out.get("hallucination_flag"),
                    retrieval_latency_ms=out.get("retrieval_latency_ms"),
                    generation_latency_ms=out.get("generation_latency_ms"),
                    total_latency_ms=out.get("total_latency_ms", elapsed_ms),
                    prompt_tokens=out.get("prompt_tokens"),
                    completion_tokens=out.get("completion_tokens"),
                    total_tokens=out.get("total_tokens"),
                    estimated_cost_usd=out.get("estimated_cost_usd"),
                    top_sources=out.get("sources", []),
                    metadata_json=out.get("metadata_json"),
                )
            )
        except Exception:
            # Telemetry should never break chat responses.
            pass
