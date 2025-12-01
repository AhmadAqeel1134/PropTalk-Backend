"""
Agent Dashboard Service - Calculates dashboard statistics
Optimized with database aggregations for performance
"""
from typing import Dict
from sqlalchemy import select, func, case, cast, Boolean
from app.database.connection import AsyncSessionLocal
from app.models.property import Property
from app.models.document import Document
from app.models.contact import Contact
from app.models.phone_number import PhoneNumber


async def get_agent_dashboard_stats(agent_id: str) -> Dict:
    """
    Get comprehensive dashboard statistics for an agent
    Optimized with single queries and aggregations
    Ready for Twilio integration (phone number status)
    """
    async with AsyncSessionLocal() as session:
        # Get all stats in parallel using single queries with aggregations
        
        # 1. Properties stats - single query
        properties_stmt = select(
            func.count(Property.id).label('total'),
            func.sum(case((Property.is_available == 'true', 1), else_=0)).label('available'),
            func.sum(case((Property.is_available == 'false', 1), else_=0)).label('unavailable'),
            func.count(func.distinct(Property.property_type)).label('types_count')
        ).where(Property.real_estate_agent_id == agent_id)
        
        properties_result = await session.execute(properties_stmt)
        properties_stats = properties_result.first()
        
        # 2. Properties by type breakdown
        properties_by_type_stmt = select(
            Property.property_type,
            func.count(Property.id).label('count')
        ).where(
            Property.real_estate_agent_id == agent_id,
            Property.property_type.isnot(None)
        ).group_by(Property.property_type)
        
        properties_by_type_result = await session.execute(properties_by_type_stmt)
        properties_by_type = {
            row[0]: row[1] 
            for row in properties_by_type_result.all()
        }
        
        # 3. Documents count - single query
        documents_stmt = select(func.count(Document.id)).where(
            Document.real_estate_agent_id == agent_id
        )
        documents_result = await session.execute(documents_stmt)
        total_documents = documents_result.scalar() or 0
        
        # 4. Contacts count - single query
        contacts_stmt = select(func.count(Contact.id)).where(
            Contact.real_estate_agent_id == agent_id
        )
        contacts_result = await session.execute(contacts_stmt)
        total_contacts = contacts_result.scalar() or 0
        
        # 5. Phone number status - single query (for Twilio integration)
        phone_number_stmt = select(PhoneNumber).where(
            PhoneNumber.real_estate_agent_id == agent_id,
            PhoneNumber.is_active == True
        )
        phone_number_result = await session.execute(phone_number_stmt)
        phone_number = phone_number_result.scalar_one_or_none()
        has_phone_number = phone_number is not None
        
        # 6. Recent properties (last 5) - optimized query
        recent_properties_stmt = select(Property).where(
            Property.real_estate_agent_id == agent_id
        ).order_by(Property.created_at.desc()).limit(5)
        
        recent_properties_result = await session.execute(recent_properties_stmt)
        recent_properties = recent_properties_result.scalars().all()
        
        recent_properties_list = [
            {
                "id": prop.id,
                "address": prop.address,
                "city": prop.city,
                "property_type": prop.property_type,
                "price": str(prop.price) if prop.price else None,
                "is_available": prop.is_available,
                "created_at": prop.created_at.isoformat() if prop.created_at else "",
            }
            for prop in recent_properties
        ]
        
        # 7. Recent contacts (last 5) - optimized query
        recent_contacts_stmt = select(Contact).where(
            Contact.real_estate_agent_id == agent_id
        ).order_by(Contact.created_at.desc()).limit(5)
        
        recent_contacts_result = await session.execute(recent_contacts_stmt)
        recent_contacts = recent_contacts_result.scalars().all()
        
        recent_contacts_list = [
            {
                "id": contact.id,
                "name": contact.name,
                "phone_number": contact.phone_number,
                "email": contact.email,
                "created_at": contact.created_at.isoformat() if contact.created_at else "",
            }
            for contact in recent_contacts
        ]
        
        # 8. Get contacts with properties count
        contacts_with_props_stmt = select(
            func.count(func.distinct(Property.contact_id))
        ).where(
            Property.real_estate_agent_id == agent_id,
            Property.contact_id.isnot(None)
        )
        contacts_with_props_result = await session.execute(contacts_with_props_stmt)
        contacts_with_properties = contacts_with_props_result.scalar() or 0
        
        # 9. Get agent verification status
        from app.services.real_estate_agent_service import get_real_estate_agent_by_id
        agent = await get_real_estate_agent_by_id(agent_id)
        is_verified = agent.get("is_verified", False) if agent else False
        
        return {
            "total_properties": properties_stats.total or 0,
            "available_properties": properties_stats.available or 0,
            "unavailable_properties": properties_stats.unavailable or 0,
            "properties_by_type": properties_by_type,
            "total_documents": total_documents,
            "total_contacts": total_contacts,
            "contacts_with_properties": contacts_with_properties,
            "has_phone_number": has_phone_number,
            "phone_number": phone_number.twilio_phone_number if phone_number else None,
            "is_verified": is_verified,
            "recent_properties": recent_properties_list,
            "recent_contacts": recent_contacts_list,
        }

