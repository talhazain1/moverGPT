"""add rating to chat_messages

Revision ID: 20240417_add_rating_to_chat_messages
Revises: 
Create Date: 2024-04-17 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '20240417_add_rating_to_chat_messages'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Get the inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if the column exists before trying to add it
    columns = [col['name'] for col in inspector.get_columns('chat_messages')]
    
    if 'rating' not in columns:
        op.add_column('chat_messages', sa.Column('rating', sa.Integer(), nullable=True))

def downgrade():
    # Get the inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if the column exists before trying to remove it
    columns = [col['name'] for col in inspector.get_columns('chat_messages')]
    
    if 'rating' in columns:
        op.drop_column('chat_messages', 'rating') 