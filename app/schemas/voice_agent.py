from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class VoiceAgentRequestResponse(BaseModel):
    """Response schema for voice agent request"""
    id: str
    real_estate_agent_id: str
    status: str  # 'pending', 'approved', 'rejected'
    requested_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: str
    updated_at: str
    # Denormalized agent info for admin UI
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    # Related voice agent / phone info (if already approved)
    voice_agent_id: Optional[str] = None
    voice_agent_phone_number: Optional[str] = None

    class Config:
        from_attributes = True


class VoiceAgentResponse(BaseModel):
    """Response schema for voice agent"""
    id: str
    real_estate_agent_id: str
    phone_number_id: Optional[str] = None
    phone_number: Optional[str] = None  # Twilio phone number (from relationship)
    name: str
    system_prompt: Optional[str] = None
    use_default_prompt: bool
    status: str  # 'active', 'inactive', 'pending_setup'
    settings: Dict = Field(default_factory=dict)
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class VoiceAgentUpdateRequest(BaseModel):
    """Request schema for updating voice agent"""
    name: Optional[str] = None
    use_default_prompt: Optional[bool] = None
    system_prompt: Optional[str] = None
    settings: Optional[Dict] = None


class VoiceAgentStatusUpdateRequest(BaseModel):
    """Request schema for toggling voice agent status"""
    status: str = Field(..., pattern="^(active|inactive)$")


class VoiceAgentRequestListResponse(BaseModel):
    """Response schema for list of voice agent requests (admin)"""
    items: List[VoiceAgentRequestResponse]
    total: int


class VoiceAgentListResponse(BaseModel):
    """Response schema for list of voice agents (admin)"""
    items: List[VoiceAgentResponse]
    total: int

