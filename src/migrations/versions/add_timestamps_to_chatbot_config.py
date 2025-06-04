"""add timestamps to chatbot_config

Revision ID: add_timestamps_to_chatbot_config
Revises: 
Create Date: 2025-05-21 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'add_timestamps_to_chatbot_config'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add the created_at and updated_at columns to chatbot_configs
    op.add_column('chatbot_configs', sa.Column('created_at', sa.DateTime, nullable=True, default=datetime.utcnow))
    op.add_column('chatbot_configs', sa.Column('updated_at', sa.DateTime, nullable=True, onupdate=datetime.utcnow))
    
    # Initialize created_at to current time for existing records
    op.execute("""
        UPDATE chatbot_configs 
        SET created_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
    """)


def downgrade():
    # Remove the timestamp columns
    op.drop_column('chatbot_configs', 'created_at')
    op.drop_column('chatbot_configs', 'updated_at') 