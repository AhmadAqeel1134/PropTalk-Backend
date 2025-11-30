from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status
from typing import List, Optional
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.document_service import (
    upload_document,
    get_documents_by_agent_id,
    delete_document
)
from app.services.real_estate_agent.document_service import (
    get_document_details,
    get_document_properties,
    get_document_contacts,
)
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_endpoint(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Upload document (CSV, PDF, DOCX) and extract properties"""
    
    # Validate file type
    file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    if file_extension not in ['csv', 'pdf', 'docx']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV, PDF, and DOCX files are supported"
        )
    
    # Read file content
    file_content = await file.read()
    
    if len(file_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    try:
        document = await upload_document(
            real_estate_agent_id=agent_id,
            file_content=file_content,
            file_name=file.filename,
            file_type=file_extension,
            description=description
        )
        return DocumentUploadResponse(**document)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/my-documents", response_model=List[DocumentResponse])
async def get_my_documents(agent_id: str = Depends(get_current_real_estate_agent_id)):
    """Get all documents uploaded by current agent"""
    docs = await get_documents_by_agent_id(agent_id)
    return [DocumentResponse(**doc) for doc in docs]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Delete document and its associated properties"""
    success = await delete_document(document_id, agent_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or unauthorized"
        )


@router.get("/{document_id}", response_model=dict)
async def get_document_endpoint(
    document_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get document details with extracted data counts"""
    doc = await get_document_details(document_id, agent_id)
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return doc


@router.get("/{document_id}/properties", response_model=List[dict])
async def get_document_properties_endpoint(
    document_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get all properties extracted from a document"""
    properties = await get_document_properties(document_id, agent_id)
    return properties


@router.get("/{document_id}/contacts", response_model=List[dict])
async def get_document_contacts_endpoint(
    document_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id)
):
    """Get all contacts extracted from a document"""
    contacts = await get_document_contacts(document_id, agent_id)
    return contacts

