from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Boolean,
    Float,
    Index,
    JSON,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class RagQueryLog(Base):
    __tablename__ = "rag_query_logs"

    id = Column(String, primary_key=True)
    real_estate_agent_id = Column(
        String,
        ForeignKey("real_estate_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    end_user_id = Column(
        String,
        ForeignKey("end_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="success", index=True)
    error_message = Column(Text, nullable=True)

    rag_enabled = Column(Boolean, nullable=False, default=False)
    retrieval_k = Column(Integer, nullable=True)
    retrieved_chunks = Column(Integer, nullable=True)

    context_recall_score = Column(Float, nullable=True)
    context_precision_score = Column(Float, nullable=True)
    answer_relevance_score = Column(Float, nullable=True)
    faithfulness_score = Column(Float, nullable=True)
    correctness_score = Column(Float, nullable=True)
    citation_precision_score = Column(Float, nullable=True)
    hallucination_flag = Column(Boolean, nullable=True)

    retrieval_latency_ms = Column(Integer, nullable=True)
    generation_latency_ms = Column(Integer, nullable=True)
    total_latency_ms = Column(Integer, nullable=True)

    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)

    top_sources = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    real_estate_agent = relationship("RealEstateAgent", backref="rag_query_logs")
    end_user = relationship("EndUser", backref="rag_query_logs")

    __table_args__ = (
        Index("idx_rag_logs_agent_created", "real_estate_agent_id", "created_at"),
        Index("idx_rag_logs_agent_status", "real_estate_agent_id", "status"),
    )
