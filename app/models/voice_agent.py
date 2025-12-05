from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class VoiceAgent(Base):
    __tablename__ = "voice_agents"
    
    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(
        String, 
        ForeignKey("real_estate_agents.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True,  # One voice agent per real estate agent
        index=True
    )
    phone_number_id = Column(
        String, 
        ForeignKey("phone_numbers.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    name = Column(String, nullable=False)  # Custom name: "Sarah", "Property Assistant", etc.
    system_prompt = Column(Text, nullable=True)  # Custom system prompt (if use_default_prompt = false)
    use_default_prompt = Column(Boolean, default=True, nullable=False)
    status = Column(String, nullable=False, default="pending_setup", index=True)  # 'active', 'inactive', 'pending_setup'
    settings = Column(JSON, nullable=False, default={})  # Voice settings, greeting, commands
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    real_estate_agent = relationship("RealEstateAgent", backref="voice_agent")
    phone_number = relationship("PhoneNumber", foreign_keys=[phone_number_id])

