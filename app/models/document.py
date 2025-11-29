from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(String, ForeignKey("real_estate_agents.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # "csv", "pdf", "docx"
    file_size = Column(String, nullable=True)  # in bytes
    cloudinary_public_id = Column(String, unique=True, nullable=False)
    cloudinary_url = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship
    real_estate_agent = relationship("RealEstateAgent", backref="documents")
