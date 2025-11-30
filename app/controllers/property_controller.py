from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from app.schemas.property import PropertyResponse
from app.services.property_service import (
    get_properties_by_agent_id,
    get_property_by_id
)
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.get("/my-properties", response_model=List[PropertyResponse])
async def get_my_properties(agent_id: str = Depends(get_current_real_estate_agent_id)):
    """Get all properties for current agent (from uploaded CSV)"""
    props = await get_properties_by_agent_id(agent_id)
    return [PropertyResponse(**prop) for prop in props]


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

