from typing import List, Optional, Dict
from sqlalchemy import select, and_
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent
from app.models.voice_agent import VoiceAgent


async def list_public_agents() -> List[Dict]:
    """Verified, active agents for the end-user directory (no credentials)."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(RealEstateAgent)
            .where(
                and_(
                    RealEstateAgent.is_active.is_(True),
                    RealEstateAgent.is_verified.is_(True),
                )
            )
            .order_by(RealEstateAgent.full_name)
        )
        result = await session.execute(stmt)
        agents = result.scalars().all()
        return [
            {
                "id": a.id,
                "full_name": a.full_name,
                "company_name": a.company_name,
                "is_verified": a.is_verified,
            }
            for a in agents
        ]


async def get_public_agent_detail(agent_id: str) -> Optional[Dict]:
    async with AsyncSessionLocal() as session:
        stmt = select(RealEstateAgent).where(
            and_(
                RealEstateAgent.id == agent_id,
                RealEstateAgent.is_active.is_(True),
                RealEstateAgent.is_verified.is_(True),
            )
        )
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        if not agent:
            return None

        va_stmt = select(VoiceAgent).where(VoiceAgent.real_estate_agent_id == agent_id)
        va_result = await session.execute(va_stmt)
        voice = va_result.scalar_one_or_none()

        return {
            "id": agent.id,
            "full_name": agent.full_name,
            "company_name": agent.company_name,
            "is_verified": agent.is_verified,
            "voice_agent_name": voice.name if voice else None,
            "voice_agent_status": voice.status if voice else None,
        }
