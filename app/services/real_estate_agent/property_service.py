"""
Property Service - Enhanced property management for real estate agents
Optimized with filters and ready for Twilio integration
"""
from typing import Optional, List, Dict, Tuple
from sqlalchemy import select, or_, and_, desc, func
from app.database.connection import AsyncSessionLocal
from app.models.property import Property
import uuid


async def create_property(
    real_estate_agent_id: str,
    property_data: Dict,
    contact_id: Optional[str] = None
) -> Dict:
    """Create a new property manually (not from CSV)"""
    async with AsyncSessionLocal() as session:
        # Validate contact ownership if contact_id provided
        if contact_id:
            from app.services.real_estate_agent.contact_service import get_contact_by_id
            contact = await get_contact_by_id(contact_id, real_estate_agent_id)
            if not contact:
                raise ValueError("Contact not found or does not belong to agent")
        
        property_id = str(uuid.uuid4())
        new_property = Property(
            id=property_id,
            real_estate_agent_id=real_estate_agent_id,
            contact_id=contact_id,
            property_type=property_data.get("property_type"),
            address=property_data.get("address", ""),
            city=property_data.get("city"),
            state=property_data.get("state"),
            zip_code=property_data.get("zip_code"),
            price=str(property_data.get("price")) if property_data.get("price") else None,
            bedrooms=property_data.get("bedrooms"),
            bathrooms=property_data.get("bathrooms"),
            square_feet=property_data.get("square_feet"),
            description=property_data.get("description"),
            amenities=property_data.get("amenities"),
            owner_name=property_data.get("owner_name"),
            owner_phone=property_data.get("owner_phone", ""),
            is_available=property_data.get("is_available", "true"),
        )
        
        session.add(new_property)
        await session.commit()
        await session.refresh(new_property)
        
        return {
            "id": new_property.id,
            "real_estate_agent_id": new_property.real_estate_agent_id,
            "document_id": new_property.document_id,
            "contact_id": new_property.contact_id,
            "property_type": new_property.property_type,
            "address": new_property.address,
            "city": new_property.city,
            "state": new_property.state,
            "zip_code": new_property.zip_code,
            "price": str(new_property.price) if new_property.price else None,
            "bedrooms": new_property.bedrooms,
            "bathrooms": new_property.bathrooms,
            "square_feet": new_property.square_feet,
            "description": new_property.description,
            "amenities": new_property.amenities,
            "owner_name": new_property.owner_name,
            "owner_phone": new_property.owner_phone,
            "is_available": new_property.is_available,
            "created_at": new_property.created_at.isoformat() if new_property.created_at else "",
            "updated_at": new_property.updated_at.isoformat() if new_property.updated_at else "",
        }


async def get_properties_by_agent_id(
    real_estate_agent_id: str,
    search: Optional[str] = None,
    property_type: Optional[str] = None,
    city: Optional[str] = None,
    is_available: Optional[str] = None,
    contact_id: Optional[str] = None,
    bedrooms: Optional[int] = None,
    page: int = 1,
    page_size: int = 16,
) -> Tuple[List[dict], int]:
    """
    Get all properties for an agent with filters.
    All filtering, sorting, and pagination is done server-side for performance.
    Results are ordered by created_at DESC (latest first) by default.
    Returns (items, total).
    """
    async with AsyncSessionLocal() as session:
        # Base conditions
        conditions = [Property.real_estate_agent_id == real_estate_agent_id]

        # Apply filters (using indexed columns for performance)
        if search:
            search_pattern = f"%{search}%"
            conditions.append(
                or_(
                    Property.address.ilike(search_pattern),
                    Property.city.ilike(search_pattern),
                    Property.state.ilike(search_pattern),
                )
            )

        if property_type:
            conditions.append(Property.property_type == property_type)

        if city:
            conditions.append(Property.city.ilike(f"%{city}%"))

        if is_available:
            conditions.append(Property.is_available == is_available.lower())

        if contact_id:
            conditions.append(Property.contact_id == contact_id)
        
        if bedrooms is not None:
            conditions.append(Property.bedrooms == bedrooms)

        where_clause = and_(*conditions)

        # Total count for pagination
        count_stmt = select(func.count()).select_from(Property).where(where_clause)
        total_result = await session.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Paged query, latest first
        stmt = (
            select(Property)
            .where(where_clause)
            .order_by(desc(Property.created_at))
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )

        result = await session.execute(stmt)
        props = result.scalars().all()

        items = [
            {
                "id": prop.id,
                "real_estate_agent_id": prop.real_estate_agent_id,
                "document_id": prop.document_id,
                "contact_id": prop.contact_id,
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

        return items, total


async def get_property_by_id(property_id: str, real_estate_agent_id: str) -> Optional[dict]:
    """Get property by ID with ownership validation"""
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
            "contact_id": prop.contact_id,
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


async def update_property(
    property_id: str,
    real_estate_agent_id: str,
    update_data: Dict
) -> Optional[Dict]:
    """Update property with ownership validation"""
    async with AsyncSessionLocal() as session:
        stmt = select(Property).where(
            Property.id == property_id,
            Property.real_estate_agent_id == real_estate_agent_id
        )
        result = await session.execute(stmt)
        prop = result.scalar_one_or_none()
        
        if not prop:
            return None
        
        # Validate contact ownership if contact_id is being updated
        if "contact_id" in update_data and update_data["contact_id"]:
            from app.services.real_estate_agent.contact_service import get_contact_by_id
            contact = await get_contact_by_id(update_data["contact_id"], real_estate_agent_id)
            if not contact:
                raise ValueError("Contact not found or does not belong to agent")
        
        # Update fields
        for key, value in update_data.items():
            if hasattr(prop, key) and value is not None:
                if key == "price":
                    setattr(prop, key, str(value))
                else:
                    setattr(prop, key, value)
        
        await session.commit()
        await session.refresh(prop)
        
        return {
            "id": prop.id,
            "real_estate_agent_id": prop.real_estate_agent_id,
            "document_id": prop.document_id,
            "contact_id": prop.contact_id,
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


async def delete_property(property_id: str, real_estate_agent_id: str) -> bool:
    """Delete property with ownership validation"""
    async with AsyncSessionLocal() as session:
        stmt = select(Property).where(
            Property.id == property_id,
            Property.real_estate_agent_id == real_estate_agent_id
        )
        result = await session.execute(stmt)
        prop = result.scalar_one_or_none()
        
        if not prop:
            return False
        
        await session.delete(prop)
        await session.commit()
        
        return True

