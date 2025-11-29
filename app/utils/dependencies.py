from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.security import decode_access_token
from app.services.auth_service import get_admin_by_id
from app.services.real_estate_agent_auth_service import get_real_estate_agent_by_id

security = HTTPBearer()


async def get_current_admin_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Extract admin ID from JWT token"""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is for admin (must be admin type or no type for backward compatibility)
    token_type = payload.get("type")
    if token_type and token_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token type for this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin_id: str = payload.get("sub")
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify admin exists and is active
    admin = await get_admin_by_id(admin_id)
    if not admin or not admin.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return admin_id


async def get_current_real_estate_agent_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Extract real estate agent ID from JWT token"""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is for real estate agent
    token_type = payload.get("type")
    if token_type != "real_estate_agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token type for this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    agent_id: str = payload.get("sub")
    if agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify agent exists and is active
    agent = await get_real_estate_agent_by_id(agent_id)
    if not agent or not agent.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Real estate agent not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return agent_id

