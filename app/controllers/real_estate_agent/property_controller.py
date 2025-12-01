"""
Property Controller - Enhanced property management endpoints
Optimized with filters and ready for Twilio integration
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional
from app.schemas.property import PropertyResponse, PropertyCreateRequest, PropertyUpdateRequest, PaginatedPropertiesResponse
from app.services.real_estate_agent.property_service import (
    create_property,
    get_properties_by_agent_id,
    get_property_by_id,
    update_property,
    delete_property,
)
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.get("/my-properties", response_model=PaginatedPropertiesResponse)
async def get_my_properties(
    search: Optional[str] = None,
    property_type: Optional[str] = None,
    city: Optional[str] = None,
    is_available: Optional[str] = None,
    contact_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 16,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """
    Get all properties for current agent with filters
    Optimized with indexed columns for fast filtering
    """
    props, total = await get_properties_by_agent_id(
        real_estate_agent_id=agent_id,
        search=search,
        property_type=property_type,
        city=city,
        is_available=is_available,
        contact_id=contact_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedPropertiesResponse(
        items=[PropertyResponse(**prop) for prop in props],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property_endpoint(
    request: PropertyCreateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Create a new property manually"""
    try:
        property_data = request.dict(exclude_unset=True)
        contact_id = property_data.pop("contact_id", None)
        
        prop = await create_property(
            real_estate_agent_id=agent_id,
            property_data=property_data,
            contact_id=contact_id
        )
        return PropertyResponse(**prop)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get specific property by ID"""
    prop = await get_property_by_id(property_id, agent_id)
    
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    return PropertyResponse(**prop)


@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property_endpoint(
    property_id: str,
    request: PropertyUpdateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Update property details"""
    try:
        update_data = request.dict(exclude_unset=True)
        contact_id = update_data.pop("contact_id", None)
        if contact_id is not None:
            update_data["contact_id"] = contact_id
        
        updated_prop = await update_property(
            property_id=property_id,
            real_estate_agent_id=agent_id,
            update_data=update_data
        )
        
        if not updated_prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        return PropertyResponse(**updated_prop)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property_endpoint(
    property_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Delete a property"""
    success = await delete_property(property_id, agent_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

