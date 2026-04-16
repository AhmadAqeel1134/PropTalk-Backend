from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Float,
    Index,
    JSON,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class RagEmbeddingJob(Base):
    __tablename__ = "rag_embedding_jobs"

    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(
        String,
        ForeignKey("real_estate_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        String,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String, nullable=False, default="queued", index=True)
    embedding_model = Column(String, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    avg_chunk_chars = Column(Integer, nullable=True)
    vector_dim = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    metrics_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    real_estate_agent = relationship("RealEstateAgent", backref="rag_embedding_jobs")
    document = relationship("Document", backref="rag_embedding_jobs")

    __table_args__ = (
        Index("idx_rag_embed_agent_created", "real_estate_agent_id", "created_at"),
        Index("idx_rag_embed_agent_status", "real_estate_agent_id", "status"),
    )
