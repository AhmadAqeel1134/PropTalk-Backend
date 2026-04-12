from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


VALID_STATUSES = {"requested", "confirmed", "cancelled", "completed", "no_show"}
VALID_VISIT_TYPES = {
    "showing", "consultation", "inspection", "open_house",
    "property_visit", "office_visit", "custom_meeting",
}
VALID_SOURCES = {"voice_inbound", "voice_outbound", "manual", "web"}


class ShowingCreateRequest(BaseModel):
    """Request to create a showing (from REST API / dashboard)"""
    contact_id: Optional[str] = None
    property_id: Optional[str] = None
    caller_phone: Optional[str] = None
    caller_name: Optional[str] = None
    visit_type: str = Field(default="showing", description="showing | consultation | inspection | open_house")
    scheduled_start: datetime = Field(..., description="ISO-8601 datetime with timezone")
    scheduled_end: Optional[datetime] = None
    source: str = Field(default="manual", description="voice_inbound | voice_outbound | manual | web")
    notes: Optional[str] = None


class ShowingUpdateRequest(BaseModel):
    """Partial update for a showing"""
    contact_id: Optional[str] = None
    property_id: Optional[str] = None
    caller_name: Optional[str] = None
    visit_type: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    status: Optional[str] = Field(default=None, description="requested | confirmed | cancelled | completed | no_show")
    notes: Optional[str] = None


class ShowingResponse(BaseModel):
    """Response schema for a single showing"""
    id: str
    real_estate_agent_id: str
    voice_agent_id: Optional[str] = None
    contact_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    property_id: Optional[str] = None
    property_address: Optional[str] = None
    property_city: Optional[str] = None
    property_state: Optional[str] = None
    property_type: Optional[str] = None
    property_price: Optional[float] = None
    property_bedrooms: Optional[int] = None
    property_bathrooms: Optional[int] = None
    property_sqft: Optional[int] = None
    call_id: Optional[str] = None
    caller_phone: Optional[str] = None
    caller_name: Optional[str] = None
    visit_type: str
    scheduled_start: str
    scheduled_end: Optional[str] = None
    status: str
    source: str
    twilio_call_sid: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PaginatedShowingsResponse(BaseModel):
    """Paginated list of showings"""
    items: List[ShowingResponse]
    total: int
    page: int
    page_size: int
