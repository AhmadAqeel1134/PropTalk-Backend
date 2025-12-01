"""
Profile Controller - Agent profile management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.agent_profile import (
    AgentProfileResponse,
    AgentProfileUpdateRequest,
    PasswordChangeRequest,
)
from app.services.real_estate_agent.profile_service import (
    get_agent_profile,
    update_agent_profile,
    change_agent_password,
)
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/agent", tags=["Agent Profile"])


@router.get("/profile", response_model=AgentProfileResponse)
async def get_profile(agent_id: str = Depends(get_current_real_estate_agent_id)):
    """Get current agent's profile"""
    profile = await get_agent_profile(agent_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return AgentProfileResponse(**profile)


@router.patch("/profile", response_model=AgentProfileResponse)
async def update_profile(
    request: AgentProfileUpdateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Update agent profile"""
    try:
        update_data = request.dict(exclude_unset=True)
        updated_profile = await update_agent_profile(agent_id, update_data)
        
        if not updated_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        return AgentProfileResponse(**updated_profile)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: PasswordChangeRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Change agent password"""
    try:
        success = await change_agent_password(
            agent_id=agent_id,
            old_password=request.old_password,
            new_password=request.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

