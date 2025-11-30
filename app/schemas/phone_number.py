from pydantic import BaseModel
from typing import Optional


class PhoneNumberResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    twilio_phone_number: str
    twilio_sid: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PhoneNumberUpdateRequest(BaseModel):
    is_active: Optional[bool] = None

