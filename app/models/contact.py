from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(String, ForeignKey("real_estate_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False, index=True)  # Indexed for fast lookups and Twilio calls
    email = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    real_estate_agent = relationship("RealEstateAgent", backref="contacts")
    
    # Composite index for fast lookups by agent and phone (for deduplication)
    __table_args__ = (
        Index('idx_agent_phone', 'real_estate_agent_id', 'phone_number'),
    )

