from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.auth import (
    RealEstateAgentRegisterRequest,
    RealEstateAgentLoginRequest,
    TokenResponse,
    RealEstateAgentAuthResponse
)
from app.services.real_estate_agent_auth_service import (
    register_real_estate_agent,
    authenticate_real_estate_agent,
    get_real_estate_agent_by_id
)
from app.utils.security import create_access_token
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/real-estate-agent/register", response_model=RealEstateAgentAuthResponse, status_code=status.HTTP_201_CREATED)
async def register_agent_endpoint(request: RealEstateAgentRegisterRequest):
    """Register a new real estate agent"""
    try:
        agent = await register_real_estate_agent(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            company_name=request.company_name,
            phone=request.phone,
            address=request.address
        )
        return RealEstateAgentAuthResponse(**agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/real-estate-agent/login", response_model=TokenResponse)
async def login_agent(request: RealEstateAgentLoginRequest):
    """Login real estate agent and get access token"""
    agent = await authenticate_real_estate_agent(email=request.email, password=request.password)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": agent["id"], "email": agent["email"], "type": "real_estate_agent"})
    
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/real-estate-agent/me", response_model=RealEstateAgentAuthResponse)
async def get_current_agent(agent_id: str = Depends(get_current_real_estate_agent_id)):
    """Get current logged-in real estate agent"""
    agent = await get_real_estate_agent_by_id(agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Real estate agent not found"
        )
    
    return RealEstateAgentAuthResponse(
        id=agent["id"],
        email=agent["email"],
        full_name=agent["full_name"],
        company_name=agent["company_name"],
        phone=agent["phone"],
        address=agent["address"],
        is_active=agent["is_active"],
        is_verified=agent["is_verified"],
        created_at="",
    )

