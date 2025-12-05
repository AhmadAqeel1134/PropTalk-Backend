from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Call(Base):
    __tablename__ = "calls"
    
    id = Column(String, primary_key=True)
    voice_agent_id = Column(
        String, 
        ForeignKey("voice_agents.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    real_estate_agent_id = Column(
        String, 
        ForeignKey("real_estate_agents.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    twilio_call_sid = Column(String, unique=True, nullable=False, index=True)  # Twilio Call SID
    contact_id = Column(
        String, 
        ForeignKey("contacts.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    from_number = Column(String, nullable=False)  # Caller's phone number
    to_number = Column(String, nullable=False)  # Voice agent's Twilio number
    status = Column(String, nullable=False, index=True)  # 'initiated', 'ringing', 'in-progress', 'completed', 'failed', 'busy', 'no-answer'
    direction = Column(String, nullable=False, index=True)  # 'inbound' | 'outbound'
    duration_seconds = Column(Integer, default=0, nullable=False)
    recording_url = Column(Text, nullable=True)  # Twilio recording URL
    recording_sid = Column(String, nullable=True, index=True)  # Twilio Recording SID
    transcript = Column(Text, nullable=True)  # STT transcript (if available)
    started_at = Column(DateTime(timezone=True), nullable=True)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    voice_agent = relationship("VoiceAgent", backref="calls")
    real_estate_agent = relationship("RealEstateAgent", backref="calls")
    contact = relationship("Contact", foreign_keys=[contact_id])
    
    # Composite indexes for fast queries
    __table_args__ = (
        Index('idx_calls_agent_created', 'real_estate_agent_id', 'created_at'),
        Index('idx_calls_agent_status', 'real_estate_agent_id', 'status'),
        Index('idx_calls_voice_agent_created', 'voice_agent_id', 'created_at'),
    )

