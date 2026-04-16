"""add rag embedding jobs table

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_embedding_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("real_estate_agent_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("avg_chunk_chars", sa.Integer(), nullable=True),
        sa.Column("vector_dim", sa.Integer(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["real_estate_agent_id"], ["real_estate_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_embedding_jobs_real_estate_agent_id", "rag_embedding_jobs", ["real_estate_agent_id"], unique=False)
    op.create_index("ix_rag_embedding_jobs_document_id", "rag_embedding_jobs", ["document_id"], unique=False)
    op.create_index("ix_rag_embedding_jobs_status", "rag_embedding_jobs", ["status"], unique=False)
    op.create_index("ix_rag_embedding_jobs_created_at", "rag_embedding_jobs", ["created_at"], unique=False)
    op.create_index("idx_rag_embed_agent_created", "rag_embedding_jobs", ["real_estate_agent_id", "created_at"], unique=False)
    op.create_index("idx_rag_embed_agent_status", "rag_embedding_jobs", ["real_estate_agent_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_rag_embed_agent_status", table_name="rag_embedding_jobs")
    op.drop_index("idx_rag_embed_agent_created", table_name="rag_embedding_jobs")
    op.drop_index("ix_rag_embedding_jobs_created_at", table_name="rag_embedding_jobs")
    op.drop_index("ix_rag_embedding_jobs_status", table_name="rag_embedding_jobs")
    op.drop_index("ix_rag_embedding_jobs_document_id", table_name="rag_embedding_jobs")
    op.drop_index("ix_rag_embedding_jobs_real_estate_agent_id", table_name="rag_embedding_jobs")
    op.drop_table("rag_embedding_jobs")
