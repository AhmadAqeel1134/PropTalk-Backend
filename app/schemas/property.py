from pydantic import BaseModel
from typing import Optional


class PropertyResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    document_id: Optional[str] = None
    property_type: Optional[str] = None
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    price: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    square_feet: Optional[int] = None
    description: Optional[str] = None
    amenities: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: str
    is_available: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

