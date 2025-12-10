from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class AgentProfileResponse(BaseModel):
    # Intentionally omitting internal IDs to keep UI clean
    email: str
    full_name: str
    company_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: str
    updated_at: str


class AgentProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    email: Optional[EmailStr] = None


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)

