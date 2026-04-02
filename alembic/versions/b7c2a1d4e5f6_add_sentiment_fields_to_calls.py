"""add sentiment_label and sentiment_scores to calls

Revision ID: b7c2a1d4e5f6
Revises: 4a8be0f0d3c4
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c2a1d4e5f6'
down_revision = '4a8be0f0d3c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('calls', sa.Column('sentiment_label', sa.String(length=32), nullable=True))
    op.add_column('calls', sa.Column('sentiment_scores', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('calls', 'sentiment_scores')
    op.drop_column('calls', 'sentiment_label')
