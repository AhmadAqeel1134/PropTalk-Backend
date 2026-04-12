"""add showings table

Revision ID: c3d4e5f6a7b8
Revises: b7c2a1d4e5f6
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b7c2a1d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'showings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('real_estate_agent_id', sa.String(), nullable=False),
        sa.Column('voice_agent_id', sa.String(), nullable=True),
        sa.Column('contact_id', sa.String(), nullable=True),
        sa.Column('property_id', sa.String(), nullable=True),
        sa.Column('call_id', sa.String(), nullable=True),
        sa.Column('caller_phone', sa.String(), nullable=True),
        sa.Column('caller_name', sa.String(), nullable=True),
        sa.Column('visit_type', sa.String(), nullable=False, server_default='showing'),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='requested'),
        sa.Column('source', sa.String(), nullable=False, server_default='voice_inbound'),
        sa.Column('twilio_call_sid', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['real_estate_agent_id'], ['real_estate_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['voice_agent_id'], ['voice_agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ondelete='SET NULL'),
    )

    op.create_index('ix_showings_real_estate_agent_id', 'showings', ['real_estate_agent_id'])
    op.create_index('ix_showings_voice_agent_id', 'showings', ['voice_agent_id'])
    op.create_index('ix_showings_contact_id', 'showings', ['contact_id'])
    op.create_index('ix_showings_property_id', 'showings', ['property_id'])
    op.create_index('ix_showings_status', 'showings', ['status'])
    op.create_index('ix_showings_created_at', 'showings', ['created_at'])
    op.create_index('idx_showings_agent_start', 'showings', ['real_estate_agent_id', 'scheduled_start'])
    op.create_index('idx_showings_property_start', 'showings', ['property_id', 'scheduled_start'])
    op.create_index('idx_showings_agent_status', 'showings', ['real_estate_agent_id', 'status'])


def downgrade() -> None:
    op.drop_index('idx_showings_agent_status', table_name='showings')
    op.drop_index('idx_showings_property_start', table_name='showings')
    op.drop_index('idx_showings_agent_start', table_name='showings')
    op.drop_index('ix_showings_created_at', table_name='showings')
    op.drop_index('ix_showings_status', table_name='showings')
    op.drop_index('ix_showings_property_id', table_name='showings')
    op.drop_index('ix_showings_contact_id', table_name='showings')
    op.drop_index('ix_showings_voice_agent_id', table_name='showings')
    op.drop_index('ix_showings_real_estate_agent_id', table_name='showings')
    op.drop_table('showings')
