"""Rename payment_plan to subscription_plan

Revision ID: 61bd445225e7
Revises: 
Create Date: 2024-04-17 18:57:55.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '61bd445225e7'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Get the inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if the column exists before trying to rename it
    columns = [col['name'] for col in inspector.get_columns('chatbot_configs')]
    
    with op.batch_alter_table('chatbot_configs', schema=None) as batch_op:
        if 'payment_plan' in columns:
            batch_op.alter_column('payment_plan',
                                new_column_name='subscription_plan',
                                existing_type=sa.String(length=50),
                                nullable=True)
        elif 'subscription_plan' not in columns:
            # If neither column exists, create the new one
            batch_op.add_column(sa.Column('subscription_plan', sa.String(length=50), nullable=True))

def downgrade():
    # Get the inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if the column exists before trying to rename it
    columns = [col['name'] for col in inspector.get_columns('chatbot_configs')]
    
    with op.batch_alter_table('chatbot_configs', schema=None) as batch_op:
        if 'subscription_plan' in columns:
            batch_op.alter_column('subscription_plan',
                                new_column_name='payment_plan',
                                existing_type=sa.String(length=50),
                                nullable=True)
        elif 'payment_plan' not in columns:
            # If neither column exists, create the old one
            batch_op.add_column(sa.Column('payment_plan', sa.String(length=50), nullable=True))
