from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.connection import Base


class RagDocumentChunk(Base):
    __tablename__ = "rag_document_chunks"

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
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)
    embedding_model = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", backref="rag_chunks")

    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_rag_chunk_doc_index"),)
