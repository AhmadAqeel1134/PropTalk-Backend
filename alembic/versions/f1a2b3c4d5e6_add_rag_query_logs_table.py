"""add rag query logs table

Revision ID: f1a2b3c4d5e6
Revises: e4f5a6b7c8d9
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_query_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("real_estate_agent_id", sa.String(), nullable=False),
        sa.Column("end_user_id", sa.String(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rag_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retrieval_k", sa.Integer(), nullable=True),
        sa.Column("retrieved_chunks", sa.Integer(), nullable=True),
        sa.Column("context_recall_score", sa.Float(), nullable=True),
        sa.Column("context_precision_score", sa.Float(), nullable=True),
        sa.Column("answer_relevance_score", sa.Float(), nullable=True),
        sa.Column("faithfulness_score", sa.Float(), nullable=True),
        sa.Column("correctness_score", sa.Float(), nullable=True),
        sa.Column("citation_precision_score", sa.Float(), nullable=True),
        sa.Column("hallucination_flag", sa.Boolean(), nullable=True),
        sa.Column("retrieval_latency_ms", sa.Integer(), nullable=True),
        sa.Column("generation_latency_ms", sa.Integer(), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("top_sources", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["real_estate_agent_id"], ["real_estate_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["end_user_id"], ["end_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_query_logs_real_estate_agent_id", "rag_query_logs", ["real_estate_agent_id"], unique=False)
    op.create_index("ix_rag_query_logs_end_user_id", "rag_query_logs", ["end_user_id"], unique=False)
    op.create_index("ix_rag_query_logs_status", "rag_query_logs", ["status"], unique=False)
    op.create_index("ix_rag_query_logs_created_at", "rag_query_logs", ["created_at"], unique=False)
    op.create_index("idx_rag_logs_agent_created", "rag_query_logs", ["real_estate_agent_id", "created_at"], unique=False)
    op.create_index("idx_rag_logs_agent_status", "rag_query_logs", ["real_estate_agent_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_rag_logs_agent_status", table_name="rag_query_logs")
    op.drop_index("idx_rag_logs_agent_created", table_name="rag_query_logs")
    op.drop_index("ix_rag_query_logs_created_at", table_name="rag_query_logs")
    op.drop_index("ix_rag_query_logs_status", table_name="rag_query_logs")
    op.drop_index("ix_rag_query_logs_end_user_id", table_name="rag_query_logs")
    op.drop_index("ix_rag_query_logs_real_estate_agent_id", table_name="rag_query_logs")
    op.drop_table("rag_query_logs")
