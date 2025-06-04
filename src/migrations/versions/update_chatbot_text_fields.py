"""update chatbot text fields

Revision ID: update_chatbot_text_fields
Revises: 
Create Date: 2025-04-30 18:10:27.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'update_chatbot_text_fields'
down_revision = None  # This might need to be updated based on your migration history
branch_labels = None
depends_on = None


def upgrade():
    # Change purpose and goal columns from VARCHAR(255) to TEXT
    op.alter_column('chatbot_configs', 'purpose',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=True)
    op.alter_column('chatbot_configs', 'goal',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=True)


def downgrade():
    # Change purpose and goal columns back from TEXT to VARCHAR(255)
    # Note: This might cause data truncation if the text is longer than 255 characters
    op.alter_column('chatbot_configs', 'purpose',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=True)
    op.alter_column('chatbot_configs', 'goal',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=True)
