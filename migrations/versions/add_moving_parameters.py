"""Add MovingParameters table

Revision ID: add_moving_parameters
Revises: 
Create Date: 2023-11-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'add_moving_parameters'
down_revision = None  # Update this to match your previous migration
branch_labels = None
depends_on = None


def upgrade():
    # Create moving_parameters table
    op.create_table(
        'moving_parameters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('base_rate_per_mile', sa.Float(), nullable=True, default=1.50),
        sa.Column('move_size_rates', JSON(), nullable=True),
        sa.Column('additional_service_costs', JSON(), nullable=True),
        sa.Column('rate_adjustments', JSON(), nullable=True),
        sa.Column('email_config', JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop moving_parameters table
    op.drop_table('moving_parameters') 