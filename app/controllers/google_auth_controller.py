from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.google_auth_service import verify_google_token
from app.services.auth_service import get_or_create_admin_from_google
from app.services.real_estate_agent_auth_service import get_or_create_agent_from_google
from app.utils.security import create_access_token
from app.schemas.auth import TokenResponse

router = APIRouter(prefix="/auth/google", tags=["Google Authentication"])


class GoogleTokenRequest(BaseModel):
    token: str
    user_type: str  # "admin" or "agent"


@router.post("/login", response_model=TokenResponse)
async def google_login(request: GoogleTokenRequest):
    """
    Login with Google OAuth token
    
    Args:
        request: Contains Google ID token and user type (admin/agent)
        
    Returns:
        JWT access token
    """
    try:
        # Verify Google token
        google_info = await verify_google_token(request.token)
        
        if request.user_type == "admin":
            # Get or create admin from Google
            admin = await get_or_create_admin_from_google(google_info)
            
            # Create JWT token
            access_token = create_access_token(
                data={
                    "sub": admin["id"],
                    "email": admin["email"],
                    "type": "admin"
                }
            )
            
            return TokenResponse(access_token=access_token, token_type="bearer")
            
        elif request.user_type == "agent":
            # Get or create agent from Google
            agent = await get_or_create_agent_from_google(google_info)
            
            # Create JWT token
            access_token = create_access_token(
                data={
                    "sub": agent["id"],
                    "email": agent["email"],
                    "type": "real_estate_agent"
                }
            )
            
            return TokenResponse(access_token=access_token, token_type="bearer")
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user type. Must be 'admin' or 'agent'"
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during Google authentication: {str(e)}"
        )
