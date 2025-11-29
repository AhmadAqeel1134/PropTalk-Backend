from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"
    
    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(String, ForeignKey("real_estate_agents.id", ondelete="CASCADE"), nullable=False)
    twilio_phone_number = Column(String, unique=True, nullable=False)
    twilio_sid = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship
    real_estate_agent = relationship("RealEstateAgent", backref="phone_numbers")
