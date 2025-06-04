"""empty message

Revision ID: 37ce4c1edc36
Revises: 20240417_add_rating_to_chat_messages, 61bd445225e7
Create Date: 2025-04-17 19:34:23.093863

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '37ce4c1edc36'
down_revision = ('20240417_add_rating_to_chat_messages', '61bd445225e7')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
