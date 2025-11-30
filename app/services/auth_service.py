from typing import Optional
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.admin import Admin
from app.utils.security import verify_password


async def authenticate_admin(email: str, password: str) -> Optional[dict]:
    """Authenticate admin and return admin data if valid"""
    from app.config import settings
    
    async with AsyncSessionLocal() as session:
        # Check if email is in admin whitelist first
        if email.lower() not in settings.admin_email_list:
            return None
        
        # Find admin by email
        stmt = select(Admin).where(Admin.email == email.lower())
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()
        
        if not admin:
            return None
        
        # Check if admin is active
        if not admin.is_active:
            return None
        
        # Verify password
        if not verify_password(password, admin.hashed_password):
            return None
        
        return {
            "id": admin.id,
            "email": admin.email,
            "full_name": admin.full_name,
            "is_active": admin.is_active,
            "is_super_admin": admin.is_super_admin,
        }


async def get_admin_by_id(admin_id: str) -> Optional[dict]:
    """Get admin by ID"""
    async with AsyncSessionLocal() as session:
        stmt = select(Admin).where(Admin.id == admin_id)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()
        
        if not admin:
            return None
        
        return {
            "id": admin.id,
            "email": admin.email,
            "full_name": admin.full_name,
            "is_active": admin.is_active,
            "is_super_admin": admin.is_super_admin,
        }


async def get_or_create_admin_from_google(google_info: dict) -> dict:
    """Get existing admin or create new one from Google OAuth"""
    import uuid
    from app.config import settings
    
    async with AsyncSessionLocal() as session:
        # Check if admin exists by email
        stmt = select(Admin).where(Admin.email == google_info["email"].lower())
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()
        
        if admin:
            # Admin exists, check if email is still in whitelist (security check)
            if google_info["email"].lower() not in settings.admin_email_list:
                raise ValueError("Email not authorized for admin access")
            
            # Check if admin is active
            if not admin.is_active:
                raise ValueError("Admin account is inactive")
            
            return {
                "id": admin.id,
                "email": admin.email,
                "full_name": admin.full_name,
                "is_active": admin.is_active,
                "is_super_admin": admin.is_super_admin,
            }
        
        # Check if email is in admin whitelist before creating new admin
        if google_info["email"].lower() not in settings.admin_email_list:
            raise ValueError("Email not authorized for admin access")
        
        # Create new admin from Google
        admin_id = str(uuid.uuid4())
        new_admin = Admin(
            id=admin_id,
            email=google_info["email"].lower(),
            hashed_password="",  # No password for Google auth
            full_name=google_info.get("name", ""),
            is_active=True,
            is_super_admin=False,
        )
        
        session.add(new_admin)
        await session.commit()
        await session.refresh(new_admin)
        
        return {
            "id": admin_id,
            "email": google_info["email"].lower(),
            "full_name": google_info.get("name", ""),
            "is_active": True,
            "is_super_admin": False,
        }
