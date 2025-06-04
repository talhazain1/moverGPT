"""
Setup Moving Tables Script

This script directly creates the necessary tables for moving functionality:
- moving_conversation_states: For tracking conversation state
- moving_bookings: For storing completed bookings

This is an alternative to using alembic migrations when permissions issues arise.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Database connection parameters - update these with your actual credentials
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'chatbotdb')
DB_USER = os.environ.get('DB_USER', 'myuser')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_PORT = os.environ.get('DB_PORT', '5432')

# SQL to create the moving_conversation_states table
CREATE_CONVERSATION_STATES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS moving_conversation_states (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    state VARCHAR(50) DEFAULT 'INITIAL',
    collected_info JSONB DEFAULT '{}',
    estimated_cost JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_moving_conversation_states_company_id ON moving_conversation_states (company_id);
CREATE INDEX IF NOT EXISTS ix_moving_conversation_states_session_id ON moving_conversation_states (session_id);
"""

# SQL to create the moving_bookings table
CREATE_BOOKINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS moving_bookings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    user_id INTEGER,
    booking_reference VARCHAR(50) NOT NULL,
    
    -- Customer details
    customer_name VARCHAR(100) NOT NULL,
    customer_email VARCHAR(100) NOT NULL,
    customer_phone VARCHAR(50) NOT NULL,
    
    -- Move details
    origin VARCHAR(255) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    move_size VARCHAR(50) NOT NULL,
    move_date DATE NOT NULL,
    distance_miles FLOAT,
    
    -- Service options
    has_packing BOOLEAN DEFAULT FALSE,
    has_storage BOOLEAN DEFAULT FALSE,
    
    -- Cost breakdown
    base_cost FLOAT NOT NULL,
    distance_cost FLOAT NOT NULL,
    packing_cost FLOAT DEFAULT 0.0,
    storage_cost FLOAT DEFAULT 0.0,
    additional_costs FLOAT DEFAULT 0.0,
    total_min_cost FLOAT NOT NULL,
    total_max_cost FLOAT NOT NULL,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'confirmed',
    payment_status VARCHAR(50) DEFAULT 'pending',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Additional data
    notes TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_moving_bookings_company_id ON moving_bookings (company_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_moving_bookings_booking_reference ON moving_bookings (booking_reference);
"""

def create_moving_tables():
    """Create the moving tables in the database"""
    
    connection = None
    
    try:
        # Connect to the database
        print(f"Connecting to database: {DB_NAME} on {DB_HOST}:{DB_PORT} as {DB_USER}")
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        
        # Set autocommit mode
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Create a cursor
        cursor = connection.cursor()
        
        # Create the tables
        print("Creating moving_conversation_states table...")
        cursor.execute(CREATE_CONVERSATION_STATES_TABLE_SQL)
        
        print("Creating moving_bookings table...")
        cursor.execute(CREATE_BOOKINGS_TABLE_SQL)
        
        print("Successfully created moving tables!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    create_moving_tables() 