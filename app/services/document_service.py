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
from app.services.rag.embedding_job_service import create_embedding_job
from app.services.rag.kb_indexing_service import run_kb_indexing


async def upload_document(
    real_estate_agent_id: str,
    file_content: bytes,
    file_name: str,
    file_type: str,
    description: Optional[str] = None,
    upload_kind: str = "property_import",
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
            upload_kind=upload_kind or "property_import",
        )
        
        session.add(new_document)
        await session.commit()
        await session.refresh(new_document)

        if (upload_kind or "property_import") == "knowledge_base":
            job = await create_embedding_job(
                real_estate_agent_id=real_estate_agent_id,
                document_id=document_id,
                status="processing",
                embedding_model="pending",
                chunk_count=0,
                avg_chunk_chars=0,
                vector_dim=None,
                processing_time_ms=0,
                quality_score=None,
                notes="Knowledge-base indexing started",
                metrics_json={"upload_kind": "knowledge_base"},
            )
            await run_kb_indexing(
                job_id=job["id"],
                real_estate_agent_id=real_estate_agent_id,
                document_id=document_id,
                file_content=file_content,
                file_type=file_type,
            )
            return {
                "id": document_id,
                "real_estate_agent_id": real_estate_agent_id,
                "file_name": file_name,
                "file_type": file_type,
                "file_size": str(file_size),
                "cloudinary_url": cloudinary_data["cloudinary_url"],
                "description": description,
                "upload_kind": new_document.upload_kind,
                "created_at": new_document.created_at.isoformat() if new_document.created_at else "",
            }
        
        # Parse document and extract properties + contacts
        try:
            parsed_data = await parse_document(file_content, file_type)
            parsed_properties = parsed_data.get("properties", [])
            parsed_contacts = parsed_data.get("contacts", [])
            
            print(f"\n{'='*60}")
            print(f"📊 PARSING RESULTS")
            print(f"{'='*60}")
            print(f"Properties extracted: {len(parsed_properties)}")
            print(f"Unique contacts extracted: {len(parsed_contacts)}")
            print(f"{'='*60}\n")
            
            # First, create/find contacts and build phone->contact_id mapping
            # Use normalized phone (digits only) as key for consistent lookup
            from app.services.real_estate_agent.contact_service import normalize_phone
            
            phone_to_contact_id = {}
            contacts_created = 0
            contacts_found = 0
            
            for contact_data in parsed_contacts:
                try:
                    contact = await find_or_create_contact_by_phone(
                        real_estate_agent_id=real_estate_agent_id,
                        name=contact_data["name"],
                        phone_number=contact_data["phone_number"],
                        email=contact_data.get("email")
                    )
                    # Use normalized phone (digits only) as key - this matches how we'll look it up
                    normalized_key = normalize_phone(contact_data["phone_number"])
                    phone_to_contact_id[normalized_key] = contact["id"]
                    
                    # Check if this was a new contact or existing
                    # (We can't easily tell, but we can count)
                    contacts_created += 1
                    print(f"  🔗 Contact: {contact['name']} - {normalized_key} -> {contact['id']}")
                except Exception as contact_err:
                    print(f"  ❌ Failed to create contact {contact_data.get('name', 'Unknown')}: {contact_err}")
                    continue
            
            print(f"\n✅ Created/found {contacts_created} contacts")
            print(f"📋 Contact mapping: {len(phone_to_contact_id)} phone numbers mapped\n")
            
            # Save properties to database and link to contacts
            properties_created = 0
            properties_linked = 0
            properties_unlinked = 0
            
            for prop_data in parsed_properties:
                try:
                    owner_phone = prop_data.get("owner_phone", "")
                    # Normalize phone the same way (digits only) for lookup
                    normalized_phone = normalize_phone(owner_phone)
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
                    properties_created += 1
                    
                    if contact_id:
                        properties_linked += 1
                        if properties_linked <= 5:  # Only log first 5 to avoid spam
                            print(f"  ✅ Property {properties_created}: '{prop_data.get('address', '')[:40]}...' -> Contact {contact_id}")
                    else:
                        properties_unlinked += 1
                        if properties_unlinked <= 5:  # Only log first 5
                            print(f"  ⚠️ Property {properties_created}: '{prop_data.get('address', '')[:40]}...' -> NO CONTACT (phone: {normalized_phone or 'missing'})")
                except Exception as prop_err:
                    print(f"  ❌ Failed to create property: {prop_err}")
                    continue
            
            print(f"\n✅ Created {properties_created} properties")
            print(f"🔗 Linked {properties_linked} properties to contacts")
            print(f"⚠️ {properties_unlinked} properties without contact links")
            print(f"{'='*60}\n")
            
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
            "upload_kind": new_document.upload_kind,
            "created_at": new_document.created_at.isoformat() if new_document.created_at else "",
        }


async def get_documents_by_agent_id(real_estate_agent_id: str) -> List[dict]:
    """Get all documents for a real estate agent with extracted counts"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import func
        from app.models.property import Property
        
        stmt = select(Document).where(Document.real_estate_agent_id == real_estate_agent_id).order_by(Document.created_at.desc())
        result = await session.execute(stmt)
        docs = result.scalars().all()
        
        if not docs:
            return []
        
        # Get properties counts per document in single query
        doc_ids = [doc.id for doc in docs]
        properties_stmt = select(
            Property.document_id,
            func.count(Property.id).label('count')
        ).where(
            Property.document_id.in_(doc_ids)
        ).group_by(Property.document_id)
        
        properties_result = await session.execute(properties_stmt)
        properties_counts = {row[0]: row[1] for row in properties_result.all()}
        
        # Get contacts counts per document (distinct contacts linked to properties from each doc)
        contacts_stmt = select(
            Property.document_id,
            func.count(func.distinct(Property.contact_id)).label('count')
        ).where(
            Property.document_id.in_(doc_ids),
            Property.contact_id.isnot(None)
        ).group_by(Property.document_id)
        
        contacts_result = await session.execute(contacts_stmt)
        contacts_counts = {row[0]: row[1] for row in contacts_result.all()}
        
        return [
            {
                "id": doc.id,
                "real_estate_agent_id": doc.real_estate_agent_id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "cloudinary_url": doc.cloudinary_url,
                "description": doc.description,
                "upload_kind": getattr(doc, "upload_kind", None) or "property_import",
                "properties_count": properties_counts.get(doc.id, 0),
                "contacts_count": contacts_counts.get(doc.id, 0),
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
