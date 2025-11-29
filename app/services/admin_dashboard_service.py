from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent


async def get_admin_dashboard_stats() -> dict:
    """Get admin dashboard statistics"""
    async with AsyncSessionLocal() as session:
        # Get all agents
        stmt = select(RealEstateAgent)
        result = await session.execute(stmt)
        all_agents = result.scalars().all()
        
        # Calculate statistics
        total_agents = len(all_agents)
        active_agents = sum(1 for agent in all_agents if agent.is_active)
        inactive_agents = total_agents - active_agents
        verified_agents = sum(1 for agent in all_agents if agent.is_verified)
        unverified_agents = total_agents - verified_agents
        
        return {
            "real_estate_agents": {
                "total_agents": total_agents,
                "active_agents": active_agents,
                "inactive_agents": inactive_agents,
                "verified_agents": verified_agents,
                "unverified_agents": unverified_agents,
            }
        }
