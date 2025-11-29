from pydantic import BaseModel, EmailStr
from typing import Optional


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RealEstateAgentRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class RealEstateAgentLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_super_admin: bool
    created_at: str

    class Config:
        from_attributes = True


class RealEstateAgentAuthResponse(BaseModel):
    id: str
    email: str
    full_name: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: str

    class Config:
        from_attributes = True

