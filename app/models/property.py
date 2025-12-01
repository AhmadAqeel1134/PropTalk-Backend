from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Property(Base):
    __tablename__ = "properties"
    
    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(String, ForeignKey("real_estate_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)  # Link to contact for Twilio calls
    property_type = Column(String, nullable=True, index=True)  # Indexed for filtering
    address = Column(String, nullable=False)
    city = Column(String, nullable=True, index=True)  # Indexed for filtering
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    price = Column(Numeric(12, 2), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    square_feet = Column(Integer, nullable=True)
    description = Column(String, nullable=True)
    amenities = Column(String, nullable=True)  # JSON string or comma-separated
    owner_name = Column(String, nullable=True)  # Keep for backward compatibility
    owner_phone = Column(String, nullable=False)  # Keep for backward compatibility and Twilio calls
    is_available = Column(String, default="true", index=True)  # Indexed for filtering
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    real_estate_agent = relationship("RealEstateAgent", backref="properties")
    document = relationship("Document", backref="properties")
    contact = relationship("Contact", backref="properties")  # Link to contact for Twilio integration
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_agent_available', 'real_estate_agent_id', 'is_available'),
        Index('idx_agent_type', 'real_estate_agent_id', 'property_type'),
        Index('idx_contact_properties', 'contact_id', 'is_available'),
    )
