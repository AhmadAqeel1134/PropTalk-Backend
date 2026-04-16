"""add rag_document_chunks table for KB vector RAG

Revision ID: c4d5e6f7a8b9
Revises: a1b2c3d4e5f7
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_document_chunks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("real_estate_agent_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["real_estate_agent_id"],
            ["real_estate_agents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_rag_chunk_doc_index"),
    )
    op.create_index("idx_rag_chunk_agent", "rag_document_chunks", ["real_estate_agent_id"])
    op.create_index("idx_rag_chunk_document", "rag_document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("idx_rag_chunk_document", table_name="rag_document_chunks")
    op.drop_index("idx_rag_chunk_agent", table_name="rag_document_chunks")
    op.drop_table("rag_document_chunks")
