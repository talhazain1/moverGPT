"""Remove active column from api_keys table

Revision ID: 20240430_remove_active_from_api_keys
Revises: fix_api_keys_table
Create Date: 2024-04-30 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240430_remove_active_from_api_keys'
down_revision = 'fix_api_keys_table'
branch_labels = None
depends_on = None


def upgrade():
    # Remove the active column from api_keys table since we're using status instead
    try:
        op.drop_column('api_keys', 'active')
        print("Successfully removed 'active' column from api_keys table")
    except Exception as e:
        print(f"Error removing 'active' column: {e}")
        # If the column doesn't exist, that's fine - we're trying to remove it anyway
        pass


def downgrade():
    # Add back the active column if needed
    op.add_column('api_keys', sa.Column('active', sa.Boolean(), nullable=True, server_default='true'))
