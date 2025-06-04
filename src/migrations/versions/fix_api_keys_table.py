"""Fix api_keys table

Revision ID: fix_api_keys_table
Revises: 20240417_add_rating_to_chat_messages
Create Date: 2025-04-29 17:25:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_api_keys_table'
down_revision = '20240417_add_rating_to_chat_messages'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to api_keys table
    try:
        op.add_column('api_keys', sa.Column('active', sa.Boolean(), nullable=True, server_default='true'))
    except Exception as e:
        print(f"Error adding 'active' column: {e}")
        
    try:
        op.add_column('api_keys', sa.Column('revoked_at', sa.DateTime(), nullable=True))
    except Exception as e:
        print(f"Error adding 'revoked_at' column: {e}")
        
    try:
        op.add_column('api_keys', sa.Column('status', sa.String(20), nullable=True, server_default='active'))
    except Exception as e:
        print(f"Error adding 'status' column: {e}")
        
    try:
        op.add_column('api_keys', sa.Column('subscription_plan', sa.String(50), nullable=True))
    except Exception as e:
        print(f"Error adding 'subscription_plan' column: {e}")
        
    try:
        op.add_column('api_keys', sa.Column('last_used_at', sa.DateTime(), nullable=True))
    except Exception as e:
        print(f"Error adding 'last_used_at' column: {e}")


def downgrade():
    # Remove added columns
    op.drop_column('api_keys', 'active')
    op.drop_column('api_keys', 'revoked_at')
    op.drop_column('api_keys', 'status')
    op.drop_column('api_keys', 'subscription_plan')
    op.drop_column('api_keys', 'last_used_at') 