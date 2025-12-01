from pydantic import BaseModel, Field
from typing import Optional, List


class PropertyResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    document_id: Optional[str] = None
    contact_id: Optional[str] = None  # Link to contact for Twilio integration
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


class PropertyCreateRequest(BaseModel):
    property_type: Optional[str] = None
    address: str = Field(..., min_length=1)
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    price: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    square_feet: Optional[int] = None
    description: Optional[str] = None
    amenities: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: str = Field(..., min_length=10)
    is_available: str = "true"
    contact_id: Optional[str] = None  # Link to contact


class PropertyUpdateRequest(BaseModel):
    property_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    price: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    square_feet: Optional[int] = None
    description: Optional[str] = None
    amenities: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    is_available: Optional[str] = None
    contact_id: Optional[str] = None  # Link to contact


class PaginatedPropertiesResponse(BaseModel):
    items: List[PropertyResponse]
    total: int
    page: int
    page_size: int

