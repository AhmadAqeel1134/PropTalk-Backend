from typing import Optional, List
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.property import Property


async def get_properties_by_agent_id(real_estate_agent_id: str) -> List[dict]:
    """Get all properties for a real estate agent"""
    async with AsyncSessionLocal() as session:
        stmt = select(Property).where(Property.real_estate_agent_id == real_estate_agent_id)
        result = await session.execute(stmt)
        props = result.scalars().all()
        
        return [
            {
                "id": prop.id,
                "real_estate_agent_id": prop.real_estate_agent_id,
                "document_id": prop.document_id,
                "property_type": prop.property_type,
                "address": prop.address,
                "city": prop.city,
                "state": prop.state,
                "zip_code": prop.zip_code,
                "price": str(prop.price) if prop.price else None,
                "bedrooms": prop.bedrooms,
                "bathrooms": prop.bathrooms,
                "square_feet": prop.square_feet,
                "description": prop.description,
                "amenities": prop.amenities,
                "owner_name": prop.owner_name,
                "owner_phone": prop.owner_phone,
                "is_available": prop.is_available,
                "created_at": prop.created_at.isoformat() if prop.created_at else "",
                "updated_at": prop.updated_at.isoformat() if prop.updated_at else "",
            }
            for prop in props
        ]


async def get_property_by_id(property_id: str, real_estate_agent_id: str) -> Optional[dict]:
    """Get property by ID (only if belongs to agent)"""
    async with AsyncSessionLocal() as session:
        stmt = select(Property).where(
            Property.id == property_id,
            Property.real_estate_agent_id == real_estate_agent_id
        )
        result = await session.execute(stmt)
        prop = result.scalar_one_or_none()
        
        if not prop:
            return None
        
        return {
            "id": prop.id,
            "real_estate_agent_id": prop.real_estate_agent_id,
            "document_id": prop.document_id,
            "property_type": prop.property_type,
            "address": prop.address,
            "city": prop.city,
            "state": prop.state,
            "zip_code": prop.zip_code,
            "price": str(prop.price) if prop.price else None,
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "square_feet": prop.square_feet,
            "description": prop.description,
            "amenities": prop.amenities,
            "owner_name": prop.owner_name,
            "owner_phone": prop.owner_phone,
            "is_available": prop.is_available,
            "created_at": prop.created_at.isoformat() if prop.created_at else "",
            "updated_at": prop.updated_at.isoformat() if prop.updated_at else "",
        }
