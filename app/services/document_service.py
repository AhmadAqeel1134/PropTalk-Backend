from typing import Optional, List
from datetime import datetime
import uuid
from sqlalchemy import select, delete
from app.database.connection import AsyncSessionLocal
from app.models.document import Document
from app.models.property import Property
from app.services.cloudinary_service import upload_file_to_cloudinary, delete_file_from_cloudinary
from app.services.document_parser_service import parse_document
from app.services.real_estate_agent.contact_service import find_or_create_contact_by_phone


async def upload_document(
    real_estate_agent_id: str,
    file_content: bytes,
    file_name: str,
    file_type: str,
    description: Optional[str] = None
) -> dict:
    """Upload document to Cloudinary and save metadata to database"""
    async with AsyncSessionLocal() as session:
        # Upload to Cloudinary
        file_size = len(file_content)
        cloudinary_data = upload_file_to_cloudinary(file_content, file_name, folder="documents")
        
        # Save document metadata
        document_id = str(uuid.uuid4())
        new_document = Document(
            id=document_id,
            real_estate_agent_id=real_estate_agent_id,
            file_name=file_name,
            file_type=file_type,
            file_size=str(file_size),
            cloudinary_public_id=cloudinary_data["cloudinary_public_id"],
            cloudinary_url=cloudinary_data["cloudinary_url"],
            description=description,
        )
        
        session.add(new_document)
        await session.commit()
        await session.refresh(new_document)
        
        # Parse document and extract properties + contacts
        try:
            parsed_data = await parse_document(file_content, file_type)
            parsed_properties = parsed_data.get("properties", [])
            parsed_contacts = parsed_data.get("contacts", [])
            
            # First, create/find contacts and build phone->contact_id mapping
            phone_to_contact_id = {}
            for contact_data in parsed_contacts:
                contact = await find_or_create_contact_by_phone(
                    real_estate_agent_id=real_estate_agent_id,
                    name=contact_data["name"],
                    phone_number=contact_data["phone_number"],
                    email=contact_data.get("email")
                )
                phone_to_contact_id[contact_data["phone_number"]] = contact["id"]
            
            # Save properties to database and link to contacts
            for prop_data in parsed_properties:
                owner_phone = prop_data.get("owner_phone", "")
                normalized_phone = ''.join(filter(str.isdigit, owner_phone))
                contact_id = phone_to_contact_id.get(normalized_phone)
                
                property_id = str(uuid.uuid4())
                new_property = Property(
                    id=property_id,
                    real_estate_agent_id=real_estate_agent_id,
                    document_id=document_id,
                    contact_id=contact_id,  # Link to contact for Twilio integration
                    property_type=prop_data.get("property_type"),
                    address=prop_data.get("address", ""),
                    city=prop_data.get("city"),
                    state=prop_data.get("state"),
                    zip_code=prop_data.get("zip_code"),
                    price=str(prop_data.get("price")) if prop_data.get("price") else None,
                    bedrooms=prop_data.get("bedrooms"),
                    bathrooms=prop_data.get("bathrooms"),
                    square_feet=prop_data.get("square_feet"),
                    description=prop_data.get("description"),
                    amenities=prop_data.get("amenities"),
                    owner_name=prop_data.get("owner_name"),
                    owner_phone=prop_data.get("owner_phone", ""),
                    is_available=prop_data.get("is_available", "true"),
                )
                session.add(new_property)
            
            await session.commit()
        except Exception as e:
            # Log error but don't fail document upload
            print(f"Warning: Failed to parse document: {str(e)}")
        
        return {
            "id": document_id,
            "real_estate_agent_id": real_estate_agent_id,
            "file_name": file_name,
            "file_type": file_type,
            "file_size": str(file_size),
            "cloudinary_url": cloudinary_data["cloudinary_url"],
            "description": description,
            "created_at": new_document.created_at.isoformat() if new_document.created_at else "",
        }


async def get_documents_by_agent_id(real_estate_agent_id: str) -> List[dict]:
    """Get all documents for a real estate agent"""
    async with AsyncSessionLocal() as session:
        stmt = select(Document).where(Document.real_estate_agent_id == real_estate_agent_id)
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


async def delete_document(document_id: str, real_estate_agent_id: str) -> bool:
    """Delete document and its properties"""
    async with AsyncSessionLocal() as session:
        # Get document
        stmt = select(Document).where(Document.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc or doc.real_estate_agent_id != real_estate_agent_id:
            return False
        
        # Delete from Cloudinary
        delete_file_from_cloudinary(doc.cloudinary_public_id)
        
        # Delete properties associated with document
        delete_props_stmt = delete(Property).where(Property.document_id == document_id)
        await session.execute(delete_props_stmt)
        
        # Delete document
        await session.delete(doc)
        await session.commit()
        
        return True
