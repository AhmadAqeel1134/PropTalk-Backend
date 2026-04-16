from pydantic import BaseModel
from typing import Optional, List


class DocumentResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    file_name: str
    file_type: str
    file_size: Optional[str] = None
    cloudinary_url: str
    description: Optional[str] = None
    upload_kind: str = "property_import"
    properties_count: int = 0
    contacts_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    file_name: str
    file_type: str
    file_size: str
    cloudinary_url: str
    description: Optional[str] = None
    upload_kind: str = "property_import"
    created_at: str


class PaginatedDocumentsResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int

