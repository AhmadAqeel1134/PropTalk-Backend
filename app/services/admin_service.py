from typing import Optional, List
from sqlalchemy import select, func, desc
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent
from app.models.property import Property
from app.models.document import Document
from app.models.contact import Contact
from app.models.phone_number import PhoneNumber


async def get_agent_full_details(agent_id: str) -> Optional[dict]:
    """Get full details of an agent including all related data - OPTIMIZED with single session"""
    # OPTIMIZATION: Use single session and batch queries
    async with AsyncSessionLocal() as session:
        # Get agent
        agent_stmt = select(RealEstateAgent).where(RealEstateAgent.id == agent_id)
        agent_result = await session.execute(agent_stmt)
        agent_obj = agent_result.scalar_one_or_none()
        
        if not agent_obj:
            return None
        
        agent = {
            "id": agent_obj.id,
            "email": agent_obj.email,
            "full_name": agent_obj.full_name,
            "company_name": agent_obj.company_name,
            "phone": agent_obj.phone,
            "address": agent_obj.address,
            "is_active": agent_obj.is_active,
            "is_verified": agent_obj.is_verified,
            "created_at": agent_obj.created_at.isoformat() if agent_obj.created_at else "",
            "updated_at": agent_obj.updated_at.isoformat() if agent_obj.updated_at else "",
        }
        
        # Get all related data in same session (faster than multiple sessions)
        properties_stmt = select(Property).where(Property.real_estate_agent_id == agent_id)
        documents_stmt = select(Document).where(Document.real_estate_agent_id == agent_id)
        phone_stmt = select(PhoneNumber).where(
            PhoneNumber.real_estate_agent_id == agent_id,
            PhoneNumber.is_active == True
        )
        
        # Execute queries sequentially but in same session (avoids multiple session overhead)
        properties_result = await session.execute(properties_stmt)
        documents_result = await session.execute(documents_stmt)
        phone_result = await session.execute(phone_stmt)
        
        # Process properties
        props = properties_result.scalars().all()
        properties = [
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
        
        # Process documents
        docs = documents_result.scalars().all()
        documents = [
            {
                "id": doc.id,
                "real_estate_agent_id": doc.real_estate_agent_id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "cloudinary_url": doc.cloudinary_url,
                "description": doc.description,
                "created_at": doc.created_at.isoformat() if doc.created_at else "",
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
            }
            for doc in docs
        ]
        
        # Process phone number
        phone_obj = phone_result.scalar_one_or_none()
        phone_number = None
        if phone_obj:
            phone_number = {
                "id": phone_obj.id,
                "real_estate_agent_id": phone_obj.real_estate_agent_id,
                "twilio_phone_number": phone_obj.twilio_phone_number,
                "twilio_sid": phone_obj.twilio_sid,
                "is_active": phone_obj.is_active,
                "created_at": phone_obj.created_at.isoformat() if phone_obj.created_at else "",
                "updated_at": phone_obj.updated_at.isoformat() if phone_obj.updated_at else "",
            }
        
        # Get contacts
        contacts_stmt = select(Contact).where(Contact.real_estate_agent_id == agent_id)
        contacts_result = await session.execute(contacts_stmt)
        contacts_objs = contacts_result.scalars().all()
        contacts = [
            {
                "id": c.id,
                "real_estate_agent_id": c.real_estate_agent_id,
                "name": c.name,
                "phone_number": c.phone_number,
                "email": c.email,
                "notes": c.notes,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            }
            for c in contacts_objs
        ]
        
        return {
            "agent": agent,
            "properties": properties,
            "documents": documents,
            "phone_number": phone_number,
            "contacts": contacts,
        }


async def get_agent_properties_for_admin(agent_id: str) -> Optional[List[dict]]:
    """Get all properties for an agent (admin view) - OPTIMIZED"""
    # OPTIMIZATION: Skip agent verification - if agent doesn't exist, properties will be empty anyway
    # This saves one database query per request
    async with AsyncSessionLocal() as session:
        stmt = select(Property).where(Property.real_estate_agent_id == agent_id)
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


async def get_agent_properties_paginated_for_admin(
    agent_id: str,
    page: int = 1,
    page_size: int = 16
) -> Optional[tuple[List[dict], int]]:
    """Get paginated properties for an agent (admin view)"""
    async with AsyncSessionLocal() as session:
        # Base query
        base_stmt = select(Property).where(Property.real_estate_agent_id == agent_id)
        
        # Total count
        count_stmt = select(func.count()).select_from(Property).where(Property.real_estate_agent_id == agent_id)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one() or 0
        
        # Paginated query, latest first
        stmt = (
            base_stmt
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


async def get_agent_documents_for_admin(agent_id: str) -> Optional[List[dict]]:
    """Get all documents for an agent (admin view) - OPTIMIZED"""
    # OPTIMIZATION: Skip agent verification - saves one query
    async with AsyncSessionLocal() as session:
        stmt = select(Document).where(Document.real_estate_agent_id == agent_id)
        result = await session.execute(stmt)
        docs = result.scalars().all()
        
        return [
            {
                "id": doc.id,
                "real_estate_agent_id": doc.real_estate_agent_id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "cloudinary_url": doc.cloudinary_url,
                "description": doc.description,
                "created_at": doc.created_at.isoformat() if doc.created_at else "",
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
            }
            for doc in docs
        ]


async def get_agent_documents_paginated_for_admin(
    agent_id: str,
    page: int = 1,
    page_size: int = 16
) -> Optional[tuple[List[dict], int]]:
    """Get paginated documents for an agent (admin view)"""
    async with AsyncSessionLocal() as session:
        # Base query
        base_stmt = select(Document).where(Document.real_estate_agent_id == agent_id)
        
        # Total count
        count_stmt = select(func.count()).select_from(Document).where(Document.real_estate_agent_id == agent_id)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one() or 0
        
        # Paginated query, latest first
        stmt = (
            base_stmt
            .order_by(desc(Document.created_at))
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        docs = result.scalars().all()
        
        items = [
            {
                "id": doc.id,
                "real_estate_agent_id": doc.real_estate_agent_id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "cloudinary_url": doc.cloudinary_url,
                "description": doc.description,
                "created_at": doc.created_at.isoformat() if doc.created_at else "",
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
            }
            for doc in docs
        ]
        
        return items, total


async def get_agent_contacts_for_admin(agent_id: str) -> Optional[List[dict]]:
    """Get all contacts for an agent (admin view)"""
    async with AsyncSessionLocal() as session:
        # Verify agent exists
        agent_stmt = select(RealEstateAgent).where(RealEstateAgent.id == agent_id)
        agent_result = await session.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()
        
        if not agent:
            return None
        
        # Get all contacts for this agent
        contacts_stmt = select(Contact).where(Contact.real_estate_agent_id == agent_id)
        contacts_result = await session.execute(contacts_stmt)
        contacts = contacts_result.scalars().all()
        
        return [
            {
                "id": contact.id,
                "real_estate_agent_id": contact.real_estate_agent_id,
                "name": contact.name,
                "phone_number": contact.phone_number,
                "email": contact.email,
                "notes": contact.notes,
                "created_at": contact.created_at.isoformat() if contact.created_at else "",
                "updated_at": contact.updated_at.isoformat() if contact.updated_at else "",
            }
            for contact in contacts
        ]


async def get_agent_phone_number_for_admin(agent_id: str) -> Optional[dict]:
    """Get phone number for an agent (admin view) - OPTIMIZED"""
    # OPTIMIZATION: Skip agent verification - saves one query
    async with AsyncSessionLocal() as session:
        stmt = select(PhoneNumber).where(
            PhoneNumber.real_estate_agent_id == agent_id,
            PhoneNumber.is_active == True
        )
        result = await session.execute(stmt)
        phone = result.scalar_one_or_none()
        
        if not phone:
            return None
        
        return {
            "id": phone.id,
            "real_estate_agent_id": phone.real_estate_agent_id,
            "twilio_phone_number": phone.twilio_phone_number,
            "twilio_sid": phone.twilio_sid,
            "is_active": phone.is_active,
            "created_at": phone.created_at.isoformat() if phone.created_at else "",
            "updated_at": phone.updated_at.isoformat() if phone.updated_at else "",
        }

