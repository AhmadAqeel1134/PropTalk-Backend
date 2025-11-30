"""
Contact Controller - Handles all contact-related endpoints for real estate agents
Optimized and ready for Twilio integration
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from app.schemas.contact import (
    ContactCreateRequest,
    ContactUpdateRequest,
    ContactResponse,
    ContactWithPropertiesResponse,
)
from app.services.real_estate_agent.contact_service import (
    create_contact,
    get_contacts_by_agent_id,
    get_contact_by_id,
    update_contact,
    delete_contact,
    get_contact_properties,
)
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.get("/my-contacts", response_model=List[ContactWithPropertiesResponse])
async def get_my_contacts(
    search: Optional[str] = None,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """
    Get all contacts for current agent with optional search
    Returns contacts with property counts (optimized for Twilio integration)
    """
    contacts = await get_contacts_by_agent_id(
        real_estate_agent_id=agent_id,
        search=search,
        include_properties=True
    )
    
    return [ContactWithPropertiesResponse(**contact) for contact in contacts]


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get single contact by ID (for Twilio calling)"""
    contact = await get_contact_by_id(contact_id, agent_id)
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    return ContactResponse(**contact)


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_new_contact(
    request: ContactCreateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Create a new contact manually"""
    try:
        contact = await create_contact(
            real_estate_agent_id=agent_id,
            name=request.name,
            phone_number=request.phone_number,
            email=request.email,
            notes=request.notes
        )
        return ContactResponse(**contact)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact_info(
    contact_id: str,
    request: ContactUpdateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Update contact information"""
    update_data = request.dict(exclude_unset=True)
    
    updated_contact = await update_contact(
        contact_id=contact_id,
        real_estate_agent_id=agent_id,
        update_data=update_data
    )
    
    if not updated_contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    return ContactResponse(**updated_contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_endpoint(
    contact_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Delete a contact (properties are unlinked, not deleted)"""
    success = await delete_contact(contact_id, agent_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )


@router.get("/{contact_id}/properties", response_model=List[dict])
async def get_contact_properties_endpoint(
    contact_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """
    Get all properties linked to a contact
    Used for building Twilio call context
    """
    properties = await get_contact_properties(contact_id, agent_id)
    return properties

