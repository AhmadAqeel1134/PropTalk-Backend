from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class PropertySummaryResponse(BaseModel):
    id: str
    address: str
    city: Optional[str]
    property_type: Optional[str]
    price: Optional[str]
    is_available: str
    created_at: str


class ContactSummaryResponse(BaseModel):
    id: str
    name: str
    phone_number: str
    email: Optional[str]
    created_at: str


class AgentDashboardStatsResponse(BaseModel):
    total_properties: int
    available_properties: int
    unavailable_properties: int
    properties_by_type: Dict[str, int]
    total_documents: int
    total_contacts: int
    contacts_with_properties: int
    has_phone_number: bool
    phone_number: Optional[str]
    is_verified: bool
    recent_properties: List[PropertySummaryResponse]
    recent_contacts: List[ContactSummaryResponse]

