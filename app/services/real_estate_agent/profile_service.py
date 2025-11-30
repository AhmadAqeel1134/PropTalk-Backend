"""
Profile Service - Agent profile management
"""
from typing import Optional, Dict
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent
from app.utils.security import verify_password, get_password_hash


async def get_agent_profile(agent_id: str) -> Optional[Dict]:
    """Get agent profile information"""
    async with AsyncSessionLocal() as session:
        stmt = select(RealEstateAgent).where(RealEstateAgent.id == agent_id)
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        
        if not agent:
            return None
        
        return {
            "id": agent.id,
            "email": agent.email,
            "full_name": agent.full_name,
            "company_name": agent.company_name,
            "phone": agent.phone,
            "address": agent.address,
            "is_active": agent.is_active,
            "is_verified": agent.is_verified,
            "created_at": agent.created_at.isoformat() if agent.created_at else "",
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else "",
        }


async def update_agent_profile(agent_id: str, update_data: Dict) -> Optional[Dict]:
    """Update agent profile information"""
    async with AsyncSessionLocal() as session:
        stmt = select(RealEstateAgent).where(RealEstateAgent.id == agent_id)
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        
        if not agent:
            return None
        
        # Check email uniqueness if email is being changed
        if "email" in update_data and update_data["email"] != agent.email:
            email_stmt = select(RealEstateAgent).where(
                RealEstateAgent.email == update_data["email"].lower(),
                RealEstateAgent.id != agent_id
            )
            email_result = await session.execute(email_stmt)
            existing_agent = email_result.scalar_one_or_none()
            if existing_agent:
                raise ValueError("Email already in use")
        
        # Update fields
        if "full_name" in update_data:
            agent.full_name = update_data["full_name"]
        if "company_name" in update_data:
            agent.company_name = update_data["company_name"]
        if "phone" in update_data:
            agent.phone = update_data["phone"]
        if "address" in update_data:
            agent.address = update_data["address"]
        if "email" in update_data:
            agent.email = update_data["email"].lower()
        
        await session.commit()
        await session.refresh(agent)
        
        return {
            "id": agent.id,
            "email": agent.email,
            "full_name": agent.full_name,
            "company_name": agent.company_name,
            "phone": agent.phone,
            "address": agent.address,
            "is_active": agent.is_active,
            "is_verified": agent.is_verified,
            "created_at": agent.created_at.isoformat() if agent.created_at else "",
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else "",
        }


async def change_agent_password(agent_id: str, old_password: str, new_password: str) -> bool:
    """Change agent password with old password verification"""
    async with AsyncSessionLocal() as session:
        stmt = select(RealEstateAgent).where(RealEstateAgent.id == agent_id)
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        
        if not agent:
            return False
        
        # Verify old password
        if not verify_password(old_password, agent.hashed_password):
            raise ValueError("Incorrect old password")
        
        # Update password
        agent.hashed_password = get_password_hash(new_password)
        await session.commit()
        
        return True

