"""
One-time script to fix booking records where session_id might be stored as string instead of integer.
Run this script after updating the MovingBooking model to use integer session_id.
"""

import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection parameters - get from environment or use defaults
# Check if we're in a Docker environment
if os.path.exists("/.dockerenv"):
    DB_HOST = os.environ.get('DB_HOST', 'postgres')
else:
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'chatbot_platform')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')

def main():
    """Main function to fix moving_bookings table."""
    conn = None
    try:
        # Connect to the database
        logger.info(f"Connecting to database: {DB_NAME} on {DB_HOST}:{DB_PORT}")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        # Create a cursor that returns results as dictionaries
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        # First check if any string session IDs exist
        cursor.execute("SELECT id, session_id FROM moving_bookings WHERE session_id::text ~ '^[0-9]+$' AND session_id::text != session_id::integer::text")
        string_session_ids = cursor.fetchall()
        
        if not string_session_ids:
            logger.info("No string session IDs found. No fixes needed.")
            return
            
        logger.info(f"Found {len(string_session_ids)} booking records with string session IDs that need fixing")
        
        # Begin a transaction
        conn.autocommit = False
        
        # Fix each booking record
        fixed_count = 0
        for booking in string_session_ids:
            booking_id = booking['id']
            old_session_id = booking['session_id']
            
            try:
                # Convert string to integer if possible
                new_session_id = int(old_session_id)
                
                # Update the record
                cursor.execute(
                    "UPDATE moving_bookings SET session_id = %s WHERE id = %s",
                    (new_session_id, booking_id)
                )
                fixed_count += 1
                logger.info(f"Fixed booking ID {booking_id}: session_id '{old_session_id}' -> {new_session_id}")
                
            except (ValueError, TypeError) as e:
                logger.error(f"Could not convert session_id '{old_session_id}' to integer for booking ID {booking_id}: {e}")
        
        # Commit the transaction
        conn.commit()
        logger.info(f"Successfully fixed {fixed_count} booking records")
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error fixing bookings: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main() 