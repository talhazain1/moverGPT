"""add api_keys table

Revision ID: add_api_keys_table
Revises: 
Create Date: 2025-05-13 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_api_keys_table'
down_revision = None  # Modify this if you have other migrations
branch_labels = None
depends_on = None


def upgrade():
    # Create the api_keys table if it doesn't exist
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )


def downgrade():
    # Drop the api_keys table
    op.drop_table('api_keys') 