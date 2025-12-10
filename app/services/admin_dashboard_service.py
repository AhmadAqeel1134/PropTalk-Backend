from sqlalchemy import select, func, case
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent
from app.models.property import Property
from app.models.document import Document
from app.models.phone_number import PhoneNumber
from app.models.contact import Contact


async def get_admin_dashboard_stats() -> dict:
    """Get admin dashboard statistics - OPTIMIZED with database aggregations"""
    async with AsyncSessionLocal() as session:
        # OPTIMIZATION: Use database aggregations instead of loading all data into memory
        # Agent statistics - single query with aggregations
        agent_stats_stmt = select(
            func.count(RealEstateAgent.id).label('total'),
            func.sum(case((RealEstateAgent.is_active == True, 1), else_=0)).label('active'),
            func.sum(case((RealEstateAgent.is_verified == True, 1), else_=0)).label('verified')
        )
        agent_stats_result = await session.execute(agent_stats_stmt)
        agent_stats = agent_stats_result.first()
        
        total_agents = agent_stats.total or 0
        active_agents = agent_stats.active or 0
        inactive_agents = total_agents - active_agents
        verified_agents = agent_stats.verified or 0
        unverified_agents = total_agents - verified_agents
        
        # Overall statistics - single queries with COUNT
        total_properties_stmt = select(func.count(Property.id))
        total_properties_result = await session.execute(total_properties_stmt)
        total_properties = total_properties_result.scalar() or 0
        
        total_documents_stmt = select(func.count(Document.id))
        total_documents_result = await session.execute(total_documents_stmt)
        total_documents = total_documents_result.scalar() or 0
        
        total_phone_numbers_stmt = select(func.count(PhoneNumber.id)).where(PhoneNumber.is_active == True)
        total_phone_numbers_result = await session.execute(total_phone_numbers_stmt)
        total_phone_numbers = total_phone_numbers_result.scalar() or 0
        
        # Contacts count
        total_contacts_stmt = select(func.count(Contact.id))
        total_contacts_result = await session.execute(total_contacts_stmt)
        total_contacts = total_contacts_result.scalar() or 0
        
        return {
            "real_estate_agents": {
                "total_agents": total_agents,
                "active_agents": active_agents,
                "inactive_agents": inactive_agents,
                "verified_agents": verified_agents,
                "unverified_agents": unverified_agents,
            },
            "overall_stats": {
                "total_properties": total_properties,
                "total_documents": total_documents,
                "total_phone_numbers": total_phone_numbers,
                "total_contacts": total_contacts,
            }
        }
