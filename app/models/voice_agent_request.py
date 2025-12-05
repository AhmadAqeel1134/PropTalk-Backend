from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class VoiceAgentRequest(Base):
    __tablename__ = "voice_agent_requests"
    
    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(
        String, 
        ForeignKey("real_estate_agents.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    status = Column(String, nullable=False, default="pending", index=True)  # 'pending', 'approved', 'rejected'
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)  # Admin who reviewed
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    real_estate_agent = relationship("RealEstateAgent", backref="voice_agent_requests")
    reviewer = relationship("Admin", foreign_keys=[reviewed_by])
    
    # Index for fast lookup of pending requests
    __table_args__ = (
        Index('idx_voice_agent_request_agent_status', 'real_estate_agent_id', 'status'),
    )

