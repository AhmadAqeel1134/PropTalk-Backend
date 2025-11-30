from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Property(Base):
    __tablename__ = "properties"
    
    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(String, ForeignKey("real_estate_agents.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    property_type = Column(String, nullable=True)  # "house", "apartment", "condo", etc.
    address = Column(String, nullable=False)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    price = Column(Numeric(12, 2), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    square_feet = Column(Integer, nullable=True)
    description = Column(String, nullable=True)
    amenities = Column(String, nullable=True)  # JSON string or comma-separated
    owner_name = Column(String, nullable=True)
    owner_phone = Column(String, nullable=False)  # Property owner phone number (for calling)
    is_available = Column(String, default="true")  # "true", "false"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    real_estate_agent = relationship("RealEstateAgent", backref="properties")
    document = relationship("Document", backref="properties")
