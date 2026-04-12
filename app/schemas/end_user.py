from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class EndUserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    phone_number: Optional[str] = None


class EndUserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class EndUserMeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone_number: Optional[str] = None
    phone_saved_at: Optional[str] = None
    is_active: bool
    created_at: str


class EndUserPhoneUpdateRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, description="Digits or E.164; stored normalized")


class PublicAgentListItem(BaseModel):
    id: str
    full_name: str
    company_name: Optional[str] = None
    is_verified: bool


class PublicAgentDetailResponse(BaseModel):
    id: str
    full_name: str
    company_name: Optional[str] = None
    is_verified: bool
    voice_agent_name: Optional[str] = None
    voice_agent_status: Optional[str] = None


class UserChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class UserChatResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
    rag_enabled: bool = False
