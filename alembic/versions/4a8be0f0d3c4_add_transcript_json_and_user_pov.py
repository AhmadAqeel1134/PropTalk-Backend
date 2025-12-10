"""add transcript_json and user_pov_summary to calls

Revision ID: 4a8be0f0d3c4
Revises: 423ec09828ad
Create Date: 2025-12-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a8be0f0d3c4'
down_revision = '423ec09828ad'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('calls', sa.Column('transcript_json', sa.JSON(), nullable=True))
    op.add_column('calls', sa.Column('user_pov_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('calls', 'user_pov_summary')
    op.drop_column('calls', 'transcript_json')

