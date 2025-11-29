from pydantic import BaseModel
from typing import List, Optional
from app.schemas.property import PropertyResponse
from app.schemas.document import DocumentResponse
from app.schemas.phone_number import PhoneNumberResponse
from app.schemas.real_estate_agent import RealEstateAgentResponse


class AgentFullDetailsResponse(BaseModel):
    """Full details of an agent including all related data"""
    agent: RealEstateAgentResponse
    properties: List[PropertyResponse]
    documents: List[DocumentResponse]
    phone_number: Optional[PhoneNumberResponse] = None
    contacts: List[dict] = []  # Will be ContactResponse when Contact model is created

