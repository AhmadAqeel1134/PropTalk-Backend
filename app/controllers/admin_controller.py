from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from app.schemas.real_estate_agent import RealEstateAgentResponse, RealEstateAgentUpdateRequest
from app.schemas.admin_dashboard import AdminDashboardResponse
from app.schemas.admin import AgentFullDetailsResponse
from app.schemas.property import PropertyResponse, PaginatedPropertiesResponse
from app.schemas.document import DocumentResponse, PaginatedDocumentsResponse
from app.schemas.phone_number import PhoneNumberResponse
from app.services.real_estate_agent_service import (
    get_all_real_estate_agents,
    get_real_estate_agent_by_id,
    update_real_estate_agent
)
from app.services.admin_dashboard_service import get_admin_dashboard_stats
from app.services.admin_service import (
    get_agent_full_details,
    get_agent_properties_for_admin,
    get_agent_properties_paginated_for_admin,
    get_agent_documents_for_admin,
    get_agent_documents_paginated_for_admin,
    get_agent_contacts_for_admin,
    get_agent_phone_number_for_admin
)
from app.utils.dependencies import get_current_admin_id

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/real-estate-agents", response_model=List[RealEstateAgentResponse])
async def get_all_agents(
    search: Optional[str] = None,
    is_verified: Optional[bool] = None,
    is_active: Optional[bool] = None,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get all real estate agents with summary statistics and filters (Admin only)"""
    agents = await get_all_real_estate_agents(include_stats=True, search=search, is_verified=is_verified, is_active=is_active)
    return agents


@router.get("/real-estate-agents/{agent_id}", response_model=RealEstateAgentResponse)
async def get_agent_by_id(agent_id: str, admin_id: str = Depends(get_current_admin_id)):
    """Get real estate agent by ID (Admin only)"""
    agent = await get_real_estate_agent_by_id(agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return RealEstateAgentResponse(**agent)


@router.patch("/real-estate-agents/{agent_id}", response_model=RealEstateAgentResponse)
async def update_agent(
    agent_id: str,
    request: RealEstateAgentUpdateRequest,
    admin_id: str = Depends(get_current_admin_id)
):
    """Update real estate agent (Admin only)"""
    update_data = request.dict(exclude_unset=True)
    
    updated_agent = await update_real_estate_agent(agent_id, update_data)
    
    if not updated_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return RealEstateAgentResponse(**updated_agent)


@router.post("/real-estate-agents/{agent_id}/verify", response_model=RealEstateAgentResponse)
async def verify_agent(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Verify an agent (Admin only)"""
    updated_agent = await update_real_estate_agent(agent_id, {"is_verified": True})
    
    if not updated_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return RealEstateAgentResponse(**updated_agent)


@router.post("/real-estate-agents/{agent_id}/unverify", response_model=RealEstateAgentResponse)
async def unverify_agent(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Unverify an agent (Admin only)"""
    updated_agent = await update_real_estate_agent(agent_id, {"is_verified": False})
    
    if not updated_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return RealEstateAgentResponse(**updated_agent)


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_dashboard_stats(admin_id: str = Depends(get_current_admin_id)):
    """Get admin dashboard statistics (Admin only)"""
    stats = await get_admin_dashboard_stats()
    return AdminDashboardResponse(**stats)


@router.get("/real-estate-agents/{agent_id}/full-details", response_model=AgentFullDetailsResponse)
async def get_agent_full_details_endpoint(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get full details of an agent including all properties, documents, phone number, and contacts (Admin only)"""
    details = await get_agent_full_details(agent_id)
    
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return AgentFullDetailsResponse(**details)


@router.get("/real-estate-agents/{agent_id}/properties", response_model=List[PropertyResponse])
async def get_agent_properties(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get all properties for an agent (Admin only) - Legacy endpoint for full details"""
    properties = await get_agent_properties_for_admin(agent_id)
    
    if properties is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return [PropertyResponse(**prop) for prop in properties]


@router.get("/real-estate-agents/{agent_id}/properties/paginated", response_model=PaginatedPropertiesResponse)
async def get_agent_properties_paginated(
    agent_id: str,
    page: int = 1,
    page_size: int = 16,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get paginated properties for an agent (Admin only)"""
    result = await get_agent_properties_paginated_for_admin(agent_id, page=page, page_size=page_size)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    properties, total = result
    
    return PaginatedPropertiesResponse(
        items=[PropertyResponse(**prop) for prop in properties],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/real-estate-agents/{agent_id}/documents", response_model=List[DocumentResponse])
async def get_agent_documents(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get all documents for an agent (Admin only) - Legacy endpoint for full details"""
    documents = await get_agent_documents_for_admin(agent_id)
    
    if documents is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return [DocumentResponse(**doc) for doc in documents]


@router.get("/real-estate-agents/{agent_id}/documents/paginated", response_model=PaginatedDocumentsResponse)
async def get_agent_documents_paginated(
    agent_id: str,
    page: int = 1,
    page_size: int = 16,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get paginated documents for an agent (Admin only)"""
    result = await get_agent_documents_paginated_for_admin(agent_id, page=page, page_size=page_size)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    documents, total = result
    
    return PaginatedDocumentsResponse(
        items=[DocumentResponse(**doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/real-estate-agents/{agent_id}/contacts", response_model=List[dict])
async def get_agent_contacts(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get all contacts for an agent (Admin only)"""
    contacts = await get_agent_contacts_for_admin(agent_id)
    
    if contacts is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return contacts


@router.get("/real-estate-agents/{agent_id}/phone-number", response_model=PhoneNumberResponse)
async def get_agent_phone_number(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get phone number for an agent (Admin only)"""
    phone_number = await get_agent_phone_number_for_admin(agent_id)
    
    if phone_number is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found or phone number not assigned"
        )
    
    return PhoneNumberResponse(**phone_number)

