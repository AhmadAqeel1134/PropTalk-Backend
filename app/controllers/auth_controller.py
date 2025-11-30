from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.auth import AdminLoginRequest, TokenResponse, AdminResponse
from app.services.auth_service import authenticate_admin, get_admin_by_id
from app.utils.security import create_access_token
from app.utils.dependencies import get_current_admin_id

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/admin/login", response_model=TokenResponse)
async def login_admin(request: AdminLoginRequest):
    """Login admin and get access token"""
    admin = await authenticate_admin(email=request.email, password=request.password)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": admin["id"], "email": admin["email"], "type": "admin"})
    
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/admin/me", response_model=AdminResponse)
async def get_current_admin(admin_id: str = Depends(get_current_admin_id)):
    """Get current logged-in admin"""
    admin = await get_admin_by_id(admin_id)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    return AdminResponse(
        id=admin["id"],
        email=admin["email"],
        full_name=admin["full_name"],
        is_active=admin["is_active"],
        is_super_admin=admin["is_super_admin"],
        created_at="",
    )

