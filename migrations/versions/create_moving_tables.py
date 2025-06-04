"""create_moving_tables

Revision ID: 3a6ed127c9a5
Revises: add_moving_parameters
Create Date: 2023-05-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3a6ed127c9a5'
down_revision = 'add_moving_parameters'
branch_labels = None
depends_on = None


def upgrade():
    # Create moving_conversation_states table
    op.create_table(
        'moving_conversation_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=50), nullable=True, default='INITIAL'),
        sa.Column('collected_info', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('estimated_cost', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create moving_bookings table
    op.create_table(
        'moving_bookings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('booking_reference', sa.String(length=50), nullable=False),
        
        # Customer details
        sa.Column('customer_name', sa.String(length=100), nullable=False),
        sa.Column('customer_email', sa.String(length=100), nullable=False),
        sa.Column('customer_phone', sa.String(length=50), nullable=False),
        
        # Move details
        sa.Column('origin', sa.String(length=255), nullable=False),
        sa.Column('destination', sa.String(length=255), nullable=False),
        sa.Column('move_size', sa.String(length=50), nullable=False),
        sa.Column('move_date', sa.Date(), nullable=False),
        sa.Column('distance_miles', sa.Float(), nullable=True),
        
        # Service options
        sa.Column('has_packing', sa.Boolean(), default=False),
        sa.Column('has_storage', sa.Boolean(), default=False),
        
        # Cost breakdown
        sa.Column('base_cost', sa.Float(), nullable=False),
        sa.Column('distance_cost', sa.Float(), nullable=False),
        sa.Column('packing_cost', sa.Float(), default=0.0),
        sa.Column('storage_cost', sa.Float(), default=0.0),
        sa.Column('additional_costs', sa.Float(), default=0.0),
        sa.Column('total_min_cost', sa.Float(), nullable=False),
        sa.Column('total_max_cost', sa.Float(), nullable=False),
        
        # Status tracking
        sa.Column('status', sa.String(length=50), default='confirmed'),
        sa.Column('payment_status', sa.String(length=50), default='pending'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now(), onupdate=sa.func.now()),
        
        # Additional data
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_moving_conversation_states_company_id'), 'moving_conversation_states', ['company_id'], unique=False)
    op.create_index(op.f('ix_moving_conversation_states_session_id'), 'moving_conversation_states', ['session_id'], unique=False)
    op.create_index(op.f('ix_moving_bookings_company_id'), 'moving_bookings', ['company_id'], unique=False)
    op.create_index(op.f('ix_moving_bookings_booking_reference'), 'moving_bookings', ['booking_reference'], unique=True)


def downgrade():
    # Drop tables
    op.drop_table('moving_bookings')
    op.drop_table('moving_conversation_states') 