from typing import Optional, List
from sqlalchemy import select, update, func
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent
from app.models.property import Property
from app.models.document import Document
from app.models.phone_number import PhoneNumber
from app.models.contact import Contact


async def get_agent_summary_stats(agent_id: str, session) -> dict:
    """Get summary statistics for an agent"""
    # Count properties
    properties_stmt = select(func.count(Property.id)).where(Property.real_estate_agent_id == agent_id)
    properties_result = await session.execute(properties_stmt)
    properties_count = properties_result.scalar() or 0
    
    # Count documents
    documents_stmt = select(func.count(Document.id)).where(Document.real_estate_agent_id == agent_id)
    documents_result = await session.execute(documents_stmt)
    documents_count = documents_result.scalar() or 0
    
    # Check if has phone number
    phone_stmt = select(PhoneNumber).where(
        PhoneNumber.real_estate_agent_id == agent_id,
        PhoneNumber.is_active == True
    )
    phone_result = await session.execute(phone_stmt)
    has_phone_number = phone_result.scalar_one_or_none() is not None
    
    # Count contacts
    contacts_stmt = select(func.count(Contact.id)).where(Contact.real_estate_agent_id == agent_id)
    contacts_result = await session.execute(contacts_stmt)
    contacts_count = contacts_result.scalar() or 0
    
    return {
        "properties_count": properties_count,
        "documents_count": documents_count,
        "contacts_count": contacts_count,
        "has_phone_number": has_phone_number,
    }


async def get_all_real_estate_agents(
    include_stats: bool = False,
    search: Optional[str] = None,
    is_verified: Optional[bool] = None,
    is_active: Optional[bool] = None
) -> List[dict]:
    """Get all real estate agents - OPTIMIZED to avoid N+1 queries with backend filters"""
    async with AsyncSessionLocal() as session:
        stmt = select(RealEstateAgent)
        
        # Apply filters
        if is_verified is not None:
            stmt = stmt.where(RealEstateAgent.is_verified == is_verified)
        
        if is_active is not None:
            stmt = stmt.where(RealEstateAgent.is_active == is_active)
        
        if search:
            from sqlalchemy import or_
            # Use PostgreSQL's ilike for case-insensitive search
            search_pattern = f"%{search}%"
            search_filter = or_(
                RealEstateAgent.full_name.ilike(search_pattern),
                RealEstateAgent.email.ilike(search_pattern),
                RealEstateAgent.company_name.ilike(search_pattern)
            )
            stmt = stmt.where(search_filter)
        
        result = await session.execute(stmt)
        agents = result.scalars().all()
        
        agents_list = []
        
        if include_stats and agents:
            # OPTIMIZATION: Batch fetch all stats in single queries instead of per-agent
            agent_ids = [agent.id for agent in agents]
            
            # Get all property counts in one query
            from sqlalchemy import case
            properties_counts_stmt = select(
                Property.real_estate_agent_id,
                func.count(Property.id).label('count')
            ).where(
                Property.real_estate_agent_id.in_(agent_ids)
            ).group_by(Property.real_estate_agent_id)
            properties_result = await session.execute(properties_counts_stmt)
            properties_counts = {row[0]: row[1] for row in properties_result.all()}
            
            # Get all document counts in one query
            documents_counts_stmt = select(
                Document.real_estate_agent_id,
                func.count(Document.id).label('count')
            ).where(
                Document.real_estate_agent_id.in_(agent_ids)
            ).group_by(Document.real_estate_agent_id)
            documents_result = await session.execute(documents_counts_stmt)
            documents_counts = {row[0]: row[1] for row in documents_result.all()}
            
            # Get all contact counts in one query
            contacts_counts_stmt = select(
                Contact.real_estate_agent_id,
                func.count(Contact.id).label('count')
            ).where(
                Contact.real_estate_agent_id.in_(agent_ids)
            ).group_by(Contact.real_estate_agent_id)
            contacts_result = await session.execute(contacts_counts_stmt)
            contacts_counts = {row[0]: row[1] for row in contacts_result.all()}
            
            # Get all phone numbers in one query
            phone_numbers_stmt = select(PhoneNumber.real_estate_agent_id).where(
                PhoneNumber.real_estate_agent_id.in_(agent_ids),
                PhoneNumber.is_active == True
            )
            phone_result = await session.execute(phone_numbers_stmt)
            agents_with_phones = {row[0] for row in phone_result.all()}
        
        for agent in agents:
            agent_dict = {
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
            
            if include_stats:
                # Use pre-fetched counts instead of individual queries
                agent_dict["stats"] = {
                    "properties_count": properties_counts.get(agent.id, 0),
                    "documents_count": documents_counts.get(agent.id, 0),
                    "contacts_count": contacts_counts.get(agent.id, 0),
                    "has_phone_number": agent.id in agents_with_phones,
                }
            
            agents_list.append(agent_dict)
        
        return agents_list


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
