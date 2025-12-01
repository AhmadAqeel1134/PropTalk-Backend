from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


class CallResponse(BaseModel):
    """Response schema for call"""
    id: str
    voice_agent_id: str
    real_estate_agent_id: str
    twilio_call_sid: str
    contact_id: Optional[str] = None
    contact_name: Optional[str] = None  # From relationship
    from_number: str
    to_number: str
    status: str
    direction: str  # 'inbound' | 'outbound'
    duration_seconds: int
    recording_url: Optional[str] = None
    recording_sid: Optional[str] = None
    transcript: Optional[str] = None
    started_at: Optional[str] = None
    answered_at: Optional[str] = None
    ended_at: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PaginatedCallsResponse(BaseModel):
    """Response schema for paginated calls"""
    items: List[CallResponse]
    total: int
    page: int
    page_size: int


class CallInitiateRequest(BaseModel):
    """Request schema for initiating a call"""
    contact_id: Optional[str] = None
    phone_number: str = Field(..., min_length=10, description="Phone number to call (E.164 format)")


class CallBatchRequest(BaseModel):
    """Request schema for batch calls"""
    contact_ids: List[str] = Field(..., min_items=1, description="List of contact IDs to call")
    delay_seconds: int = Field(default=30, ge=0, le=300, description="Delay between calls in seconds")


class CallRecordingResponse(BaseModel):
    """Response schema for call recording"""
    recording_url: str
    recording_sid: str
    duration_seconds: int


class CallTranscriptResponse(BaseModel):
    """Response schema for call transcript"""
    transcript: str


class CallStatisticsResponse(BaseModel):
    """Response schema for call statistics"""
    period: str  # 'day' | 'week' | 'month'
    total_calls: int
    completed_calls: int
    failed_calls: int
    total_duration_seconds: int
    average_duration_seconds: float
    calls_by_status: Dict[str, int]
    calls_by_day: List[Dict[str, Union[str, int]]]  # [{"date": "2025-01-15", "count": 5}, ...]

