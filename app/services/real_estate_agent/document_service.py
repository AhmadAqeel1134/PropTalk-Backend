"""
Document Service - Enhanced document management for agents
"""
from typing import Optional, List, Dict
from sqlalchemy import select, func
from app.database.connection import AsyncSessionLocal
from app.models.document import Document
from app.models.property import Property
from app.models.contact import Contact


async def get_document_details(document_id: str, real_estate_agent_id: str) -> Optional[Dict]:
    """Get document details with extracted data counts"""
    async with AsyncSessionLocal() as session:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.real_estate_agent_id == real_estate_agent_id
        )
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            return None
        
        # Get property count
        properties_stmt = select(func.count(Property.id)).where(
            Property.document_id == document_id
        )
        properties_result = await session.execute(properties_stmt)
        properties_count = properties_result.scalar() or 0
        
        # Get contact count (contacts extracted from this document)
        # We need to find contacts that have properties from this document
        contacts_stmt = select(func.count(func.distinct(Property.contact_id))).where(
            Property.document_id == document_id,
            Property.contact_id.isnot(None)
        )
        contacts_result = await session.execute(contacts_stmt)
        contacts_count = contacts_result.scalar() or 0
        
        return {
            "id": doc.id,
            "real_estate_agent_id": doc.real_estate_agent_id,
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "cloudinary_url": doc.cloudinary_url,
            "description": doc.description,
            "properties_count": properties_count,
            "contacts_count": contacts_count,
            "created_at": doc.created_at.isoformat() if doc.created_at else "",
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
        }


async def get_document_properties(document_id: str, real_estate_agent_id: str) -> List[Dict]:
    """Get all properties extracted from a document"""
    async with AsyncSessionLocal() as session:
        # Verify document ownership
        doc_stmt = select(Document).where(
            Document.id == document_id,
            Document.real_estate_agent_id == real_estate_agent_id
        )
        doc_result = await session.execute(doc_stmt)
        doc = doc_result.scalar_one_or_none()
        
        if not doc:
            return []
        
        # Get properties
        properties_stmt = select(Property).where(Property.document_id == document_id)
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
                "contact_id": prop.contact_id,
            }
            for prop in properties
        ]


async def get_document_contacts(document_id: str, real_estate_agent_id: str) -> List[Dict]:
    """Get all contacts extracted from a document"""
    async with AsyncSessionLocal() as session:
        # Verify document ownership
        doc_stmt = select(Document).where(
            Document.id == document_id,
            Document.real_estate_agent_id == real_estate_agent_id
        )
        doc_result = await session.execute(doc_stmt)
        doc = doc_result.scalar_one_or_none()
        
        if not doc:
            return []
        
        # Get distinct contacts that have properties from this document
        contacts_stmt = select(
            Contact.id,
            Contact.name,
            Contact.phone_number,
            Contact.email,
            func.count(Property.id).label('properties_count')
        ).join(
            Property, Property.contact_id == Contact.id
        ).where(
            Property.document_id == document_id,
            Contact.real_estate_agent_id == real_estate_agent_id
        ).group_by(Contact.id, Contact.name, Contact.phone_number, Contact.email)
        
        contacts_result = await session.execute(contacts_stmt)
        contacts = contacts_result.all()
        
        return [
            {
                "id": row[0],
                "name": row[1],
                "phone_number": row[2],
                "email": row[3],
                "properties_count": row[4],
            }
            for row in contacts
        ]

