from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Showing(Base):
    __tablename__ = "showings"

    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(
        String,
        ForeignKey("real_estate_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voice_agent_id = Column(
        String,
        ForeignKey("voice_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contact_id = Column(
        String,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    property_id = Column(
        String,
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    call_id = Column(
        String,
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
    )

    caller_phone = Column(String, nullable=True)
    caller_name = Column(String, nullable=True)
    visit_type = Column(String, nullable=False, default="showing")
    scheduled_start = Column(DateTime(timezone=True), nullable=False)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="requested", index=True)
    source = Column(String, nullable=False, default="voice_inbound")
    twilio_call_sid = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    real_estate_agent = relationship("RealEstateAgent", backref="showings")
    voice_agent = relationship("VoiceAgent", backref="showings")
    contact = relationship("Contact", backref="showings")
    property = relationship("Property", backref="showings")
    call = relationship("Call", backref="showings")

    __table_args__ = (
        Index("idx_showings_agent_start", "real_estate_agent_id", "scheduled_start"),
        Index("idx_showings_property_start", "property_id", "scheduled_start"),
        Index("idx_showings_agent_status", "real_estate_agent_id", "status"),
    )
