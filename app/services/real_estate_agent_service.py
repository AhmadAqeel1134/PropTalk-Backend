from typing import Optional, List
from sqlalchemy import select, update
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent


async def get_all_real_estate_agents() -> List[dict]:
    """Get all real estate agents"""
    async with AsyncSessionLocal() as session:
        stmt = select(RealEstateAgent)
        result = await session.execute(stmt)
        agents = result.scalars().all()
        
        return [
            {
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
            for agent in agents
        ]


async def get_real_estate_agent_by_id(agent_id: str) -> Optional[dict]:
    """Get real estate agent by ID"""
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


async def update_real_estate_agent(agent_id: str, update_data: dict) -> Optional[dict]:
    """Update real estate agent"""
    async with AsyncSessionLocal() as session:
        # Check if agent exists
        stmt = select(RealEstateAgent).where(RealEstateAgent.id == agent_id)
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        
        if not agent:
            return None
        
        # Update fields
        for key, value in update_data.items():
            if value is not None:
                setattr(agent, key, value)
        
        await session.commit()
        await session.refresh(agent)
        
        # Return updated agent
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
