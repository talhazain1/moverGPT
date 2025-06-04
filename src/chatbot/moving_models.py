"""
Moving-specific Models

This module defines models for storing moving-specific conversation state and booking information.
"""

from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.mutable import MutableDict
from core.database import db

class MovingConversationState(db.Model):
    """
    Stores the state of a moving cost conversation with a user.
    This allows the conversation to be resumed even if the chat session ends.
    """
    __tablename__ = 'moving_conversation_states'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    collected_info = db.Column(MutableDict.as_mutable(JSON), default=dict)
    estimated_cost = db.Column(MutableDict.as_mutable(JSON), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<MovingConversationState id={self.id} session_id={self.session_id} state={self.state}>"

class MovingBooking(db.Model):
    """
    Stores completed moving bookings generated from chatbot interactions.
    """
    __tablename__ = 'moving_bookings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    booking_reference = db.Column(db.String(50), nullable=False)
    
    # Customer details
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    
    # Move details
    origin = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    move_size = db.Column(db.String(50), nullable=False)
    move_date = db.Column(db.Date, nullable=False)
    distance_miles = db.Column(db.Float, nullable=True)
    
    # Service options
    has_packing = db.Column(db.Boolean, default=False)
    has_storage = db.Column(db.Boolean, default=False)
    
    # Cost breakdown
    base_cost = db.Column(db.Float, nullable=False)
    distance_cost = db.Column(db.Float, nullable=False)
    packing_cost = db.Column(db.Float, default=0.0)
    storage_cost = db.Column(db.Float, default=0.0)
    additional_costs = db.Column(db.Float, default=0.0)
    total_min_cost = db.Column(db.Float, nullable=False)
    total_max_cost = db.Column(db.Float, nullable=False)
    
    # Status tracking
    status = db.Column(db.String(50), default='confirmed')  # confirmed, scheduled, completed, cancelled
    payment_status = db.Column(db.String(50), default='pending')  # pending, partial, paid
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional data
    notes = db.Column(db.Text, nullable=True)
    booking_metadata = db.Column(MutableDict.as_mutable(JSON), default=dict)
    
    def __repr__(self):
        return f"<MovingBooking id={self.id} reference={self.booking_reference} status={self.status}>"
    
    @classmethod
    def from_conversation_data(cls, company_id, session_id, collected_info, estimated_cost):
        """
        Create a booking record from conversation data
        
        Args:
            company_id (int): Company ID
            session_id (int): Session ID
            collected_info (dict): Information collected during conversation
            estimated_cost (dict): Cost estimate details
            
        Returns:
            MovingBooking: New booking record
        """
        # Generate booking reference
        booking_reference = f"MOV-{session_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        # Convert move_date string to date object
        try:
            move_date = datetime.strptime(collected_info.get('move_date', ''), '%Y-%m-%d').date()
        except ValueError:
            # Fallback to current date + 7 days if date format is invalid
            move_date = (datetime.now() + timedelta(days=7)).date()
        
        # Determine additional services
        additional_services = collected_info.get('additional_services', [])
        has_packing = 'packing' in additional_services
        has_storage = 'storage' in additional_services
        
        # Extract costs
        base_cost = estimated_cost.get('base_cost', 0)
        distance_cost = estimated_cost.get('distance_cost', 0)
        additional_services_cost = estimated_cost.get('additional_services_cost', 0)
        
        # Calculate packing and storage costs
        packing_cost = 0
        storage_cost = 0
        if additional_services_cost > 0:
            if has_packing and has_storage:
                # Split evenly if both are selected
                packing_cost = additional_services_cost / 2
                storage_cost = additional_services_cost / 2
            elif has_packing:
                packing_cost = additional_services_cost
            elif has_storage:
                storage_cost = additional_services_cost
        
        # Create booking record
        booking = cls(
            company_id=company_id,
            session_id=session_id,
            booking_reference=booking_reference,
            customer_name=collected_info.get('customer_name', ''),
            customer_email=collected_info.get('customer_email', ''),
            customer_phone=collected_info.get('customer_phone', ''),
            origin=collected_info.get('origin', ''),
            destination=collected_info.get('destination', ''),
            move_size=collected_info.get('move_size', ''),
            move_date=move_date,
            distance_miles=estimated_cost.get('distance_miles', 0),
            has_packing=has_packing,
            has_storage=has_storage,
            base_cost=base_cost,
            distance_cost=distance_cost,
            packing_cost=packing_cost,
            storage_cost=storage_cost,
            additional_costs=0,  # No other additional costs in this implementation
            total_min_cost=estimated_cost.get('min_cost', 0),
            total_max_cost=estimated_cost.get('max_cost', 0),
            booking_metadata={
                'original_collected_info': collected_info,
                'original_estimated_cost': estimated_cost
            }
        )
        
        return booking 