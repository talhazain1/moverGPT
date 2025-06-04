"""add bot_name to chat_sessions

Revision ID: add_bot_name_to_chat_sessions
Revises: 
Create Date: 2025-05-21 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_bot_name_to_chat_sessions'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add the bot_name column to chat_sessions
    op.add_column('chat_sessions', sa.Column('bot_name', sa.String(255), nullable=True))
    
    # Populate the bot_name from the corresponding chatbot
    op.execute("""
        UPDATE chat_sessions cs
        SET bot_name = cc.bot_name
        FROM chatbot_configs cc
        WHERE cs.chatbot_id = cc.id
    """)


def downgrade():
    # Remove the bot_name column
    op.drop_column('chat_sessions', 'bot_name') 