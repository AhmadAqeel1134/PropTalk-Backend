from pydantic import BaseModel, EmailStr
from typing import Optional


class AgentSummaryStats(BaseModel):
    properties_count: int
    documents_count: int
    contacts_count: int
    has_phone_number: bool


class RealEstateAgentResponse(BaseModel):
    id: str
    email: str
    full_name: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: str
    updated_at: str
    stats: Optional[AgentSummaryStats] = None

    class Config:
        from_attributes = True


class RealEstateAgentUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

