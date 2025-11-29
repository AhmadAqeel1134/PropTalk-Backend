from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from app.schemas.real_estate_agent import RealEstateAgentResponse, RealEstateAgentUpdateRequest
from app.schemas.admin_dashboard import AdminDashboardResponse
from app.services.real_estate_agent_service import (
    get_all_real_estate_agents,
    get_real_estate_agent_by_id,
    update_real_estate_agent
)
from app.services.admin_dashboard_service import get_admin_dashboard_stats
from app.utils.dependencies import get_current_admin_id

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/real-estate-agents", response_model=List[RealEstateAgentResponse])
async def get_all_agents(admin_id: str = Depends(get_current_admin_id)):
    """Get all real estate agents (Admin only)"""
    agents = await get_all_real_estate_agents()
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


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_dashboard_stats(admin_id: str = Depends(get_current_admin_id)):
    """Get admin dashboard statistics (Admin only)"""
    stats = await get_admin_dashboard_stats()
    return AdminDashboardResponse(**stats)

