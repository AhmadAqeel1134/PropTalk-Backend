"""
Contact Service - Handles all contact-related business logic
Optimized for Twilio integration (phone_number is indexed and validated)
"""
from typing import Optional, List, Dict
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.database.connection import AsyncSessionLocal
from app.models.contact import Contact
from app.models.property import Property
import uuid
import re


def normalize_phone(phone: str) -> str:
    """Normalize phone number for consistent storage and Twilio compatibility"""
    # Remove all non-digit characters
    cleaned = ''.join(filter(str.isdigit, phone))
    return cleaned


async def create_contact(
    real_estate_agent_id: str,
    name: str,
    phone_number: str,
    email: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict:
    """Create a new contact with duplicate phone check"""
    async with AsyncSessionLocal() as session:
        # Normalize phone number
        normalized_phone = normalize_phone(phone_number)
        
        # Check for duplicate phone number for this agent
        stmt = select(Contact).where(
            Contact.real_estate_agent_id == real_estate_agent_id,
            Contact.phone_number == normalized_phone
        )
        result = await session.execute(stmt)
        existing_contact = result.scalar_one_or_none()
        
        if existing_contact:
            raise ValueError(f"Contact with phone number {phone_number} already exists")
        
        # Create new contact
        contact_id = str(uuid.uuid4())
        new_contact = Contact(
            id=contact_id,
            real_estate_agent_id=real_estate_agent_id,
            name=name,
            phone_number=normalized_phone,
            email=email.lower() if email else None,
            notes=notes
        )
        
        session.add(new_contact)
        await session.commit()
        await session.refresh(new_contact)
        
        return {
            "id": new_contact.id,
            "real_estate_agent_id": new_contact.real_estate_agent_id,
            "name": new_contact.name,
            "phone_number": new_contact.phone_number,
            "email": new_contact.email,
            "notes": new_contact.notes,
            "created_at": new_contact.created_at.isoformat() if new_contact.created_at else "",
            "updated_at": new_contact.updated_at.isoformat() if new_contact.updated_at else "",
        }


async def find_or_create_contact_by_phone(
    real_estate_agent_id: str,
    name: str,
    phone_number: str,
    email: Optional[str] = None
) -> Dict:
    """
    Find existing contact by phone or create new one
    Used during CSV parsing to deduplicate contacts
    Returns contact dict for Twilio integration
    """
    async with AsyncSessionLocal() as session:
        normalized_phone = normalize_phone(phone_number)
        
        # Try to find existing contact
        stmt = select(Contact).where(
            Contact.real_estate_agent_id == real_estate_agent_id,
            Contact.phone_number == normalized_phone
        )
        result = await session.execute(stmt)
        existing_contact = result.scalar_one_or_none()
        
        if existing_contact:
            return {
                "id": existing_contact.id,
                "real_estate_agent_id": existing_contact.real_estate_agent_id,
                "name": existing_contact.name,
                "phone_number": existing_contact.phone_number,
                "email": existing_contact.email,
                "notes": existing_contact.notes,
                "created_at": existing_contact.created_at.isoformat() if existing_contact.created_at else "",
                "updated_at": existing_contact.updated_at.isoformat() if existing_contact.updated_at else "",
            }
        
        # Create new contact
        contact_id = str(uuid.uuid4())
        new_contact = Contact(
            id=contact_id,
            real_estate_agent_id=real_estate_agent_id,
            name=name,
            phone_number=normalized_phone,
            email=email.lower() if email else None
        )
        
        session.add(new_contact)
        await session.commit()
        await session.refresh(new_contact)
        
        return {
            "id": new_contact.id,
            "real_estate_agent_id": new_contact.real_estate_agent_id,
            "name": new_contact.name,
            "phone_number": new_contact.phone_number,
            "email": new_contact.email,
            "notes": new_contact.notes,
            "created_at": new_contact.created_at.isoformat() if new_contact.created_at else "",
            "updated_at": new_contact.updated_at.isoformat() if new_contact.updated_at else "",
        }


async def get_contacts_by_agent_id(
    real_estate_agent_id: str,
    search: Optional[str] = None,
    include_properties: bool = False
) -> List[Dict]:
    """
    Get all contacts for an agent with optional search and property counts
    Optimized with single query using aggregations
    """
    async with AsyncSessionLocal() as session:
        # Base query
        stmt = select(Contact).where(Contact.real_estate_agent_id == real_estate_agent_id)
        
        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Contact.name.ilike(search_pattern),
                    Contact.phone_number.ilike(search_pattern),
                    Contact.email.ilike(search_pattern) if Contact.email else False
                )
            )
        
        result = await session.execute(stmt)
        contacts = result.scalars().all()
        
        if not contacts:
            return []
        
        contact_ids = [c.id for c in contacts]
        
        # Get property counts in single query (optimized)
        if include_properties:
            properties_stmt = select(
                Property.contact_id,
                func.count(Property.id).label('count')
            ).where(
                Property.contact_id.in_(contact_ids)
            ).group_by(Property.contact_id)
            
            properties_result = await session.execute(properties_stmt)
            properties_counts = {row[0]: row[1] for row in properties_result.all()}
        else:
            properties_counts = {}
        
        # Build response
        contacts_list = []
        for contact in contacts:
            contact_dict = {
                "id": contact.id,
                "real_estate_agent_id": contact.real_estate_agent_id,
                "name": contact.name,
                "phone_number": contact.phone_number,
                "email": contact.email,
                "notes": contact.notes,
                "created_at": contact.created_at.isoformat() if contact.created_at else "",
                "updated_at": contact.updated_at.isoformat() if contact.updated_at else "",
            }
            
            if include_properties:
                contact_dict["properties_count"] = properties_counts.get(contact.id, 0)
            
            contacts_list.append(contact_dict)
        
        return contacts_list


async def get_contact_by_id(contact_id: str, real_estate_agent_id: str) -> Optional[Dict]:
    """Get single contact with ownership validation"""
    async with AsyncSessionLocal() as session:
        stmt = select(Contact).where(
            Contact.id == contact_id,
            Contact.real_estate_agent_id == real_estate_agent_id
        )
        result = await session.execute(stmt)
        contact = result.scalar_one_or_none()
        
        if not contact:
            return None
        
        return {
            "id": contact.id,
            "real_estate_agent_id": contact.real_estate_agent_id,
            "name": contact.name,
            "phone_number": contact.phone_number,
            "email": contact.email,
            "notes": contact.notes,
            "created_at": contact.created_at.isoformat() if contact.created_at else "",
            "updated_at": contact.updated_at.isoformat() if contact.updated_at else "",
        }


async def update_contact(
    contact_id: str,
    real_estate_agent_id: str,
    update_data: Dict
) -> Optional[Dict]:
    """Update contact with ownership validation"""
    async with AsyncSessionLocal() as session:
        stmt = select(Contact).where(
            Contact.id == contact_id,
            Contact.real_estate_agent_id == real_estate_agent_id
        )
        result = await session.execute(stmt)
        contact = result.scalar_one_or_none()
        
        if not contact:
            return None
        
        # Update fields
        if "name" in update_data:
            contact.name = update_data["name"]
        if "phone_number" in update_data:
            contact.phone_number = normalize_phone(update_data["phone_number"])
        if "email" in update_data:
            contact.email = update_data["email"].lower() if update_data["email"] else None
        if "notes" in update_data:
            contact.notes = update_data["notes"]
        
        await session.commit()
        await session.refresh(contact)
        
        return {
            "id": contact.id,
            "real_estate_agent_id": contact.real_estate_agent_id,
            "name": contact.name,
            "phone_number": contact.phone_number,
            "email": contact.email,
            "notes": contact.notes,
            "created_at": contact.created_at.isoformat() if contact.created_at else "",
            "updated_at": contact.updated_at.isoformat() if contact.updated_at else "",
        }


async def delete_contact(contact_id: str, real_estate_agent_id: str) -> bool:
    """Delete contact with ownership validation"""
    async with AsyncSessionLocal() as session:
        stmt = select(Contact).where(
            Contact.id == contact_id,
            Contact.real_estate_agent_id == real_estate_agent_id
        )
        result = await session.execute(stmt)
        contact = result.scalar_one_or_none()
        
        if not contact:
            return False
        
        # Unlink properties (set contact_id to NULL)
        update_properties_stmt = (
            Property.__table__.update()
            .where(Property.contact_id == contact_id)
            .values(contact_id=None)
        )
        await session.execute(update_properties_stmt)
        
        # Delete contact
        await session.delete(contact)
        await session.commit()
        
        return True


async def get_contact_properties(contact_id: str, real_estate_agent_id: str) -> List[Dict]:
    """Get all properties linked to a contact (for Twilio context)"""
    async with AsyncSessionLocal() as session:
        # Verify contact ownership first
        contact_stmt = select(Contact).where(
            Contact.id == contact_id,
            Contact.real_estate_agent_id == real_estate_agent_id
        )
        contact_result = await session.execute(contact_stmt)
        contact = contact_result.scalar_one_or_none()
        
        if not contact:
            return []
        
        # Get properties
        properties_stmt = select(Property).where(
            Property.contact_id == contact_id
        )
        properties_result = await session.execute(properties_stmt)
        properties = properties_result.scalars().all()
        
        return [
            {
                "id": prop.id,
                "address": prop.address,
                "city": prop.city,
                "state": prop.state,
                "property_type": prop.property_type,
                "price": str(prop.price) if prop.price else None,
                "is_available": prop.is_available,
            }
            for prop in properties
        ]


async def link_property_to_contact(
    property_id: str,
    contact_id: str,
    real_estate_agent_id: str
) -> bool:
    """Link property to contact (for Twilio integration)"""
    async with AsyncSessionLocal() as session:
        # Verify ownership of both property and contact
        property_stmt = select(Property).where(
            Property.id == property_id,
            Property.real_estate_agent_id == real_estate_agent_id
        )
        property_result = await session.execute(property_stmt)
        property_obj = property_result.scalar_one_or_none()
        
        if not property_obj:
            return False
        
        contact_stmt = select(Contact).where(
            Contact.id == contact_id,
            Contact.real_estate_agent_id == real_estate_agent_id
        )
        contact_result = await session.execute(contact_stmt)
        contact = contact_result.scalar_one_or_none()
        
        if not contact:
            return False
        
        # Link property to contact
        property_obj.contact_id = contact_id
        await session.commit()
        
        return True

