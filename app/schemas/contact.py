from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


class ContactCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Contact full name")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Contact phone number")
    email: Optional[EmailStr] = Field(None, description="Contact email address")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes about the contact")
    
    @validator('phone_number')
    def validate_phone(cls, v):
        # Basic phone validation - remove spaces, dashes, parentheses
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) < 10:
            raise ValueError('Phone number must contain at least 10 digits')
        return cleaned


class ContactUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    notes: Optional[str] = Field(None, max_length=1000)
    
    @validator('phone_number')
    def validate_phone(cls, v):
        if v:
            cleaned = ''.join(filter(str.isdigit, v))
            if len(cleaned) < 10:
                raise ValueError('Phone number must contain at least 10 digits')
            return cleaned
        return v


class ContactResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    name: str
    phone_number: str
    email: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ContactWithPropertiesResponse(ContactResponse):
    properties_count: int = Field(default=0, description="Number of properties linked to this contact")
    properties: Optional[List[dict]] = Field(default=None, description="List of properties (if requested)")


class ContactSummaryResponse(BaseModel):
    id: str
    name: str
    phone_number: str
    properties_count: int
    
    class Config:
        from_attributes = True

