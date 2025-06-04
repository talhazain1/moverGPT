#!/usr/bin/env python
"""
Fix Moving Quote Permissions Script

This script grants the necessary permissions to the application database user for the
moving_quote_requests table. This fixes the "permission denied for table moving_quote_requests"
error that occurs when submitting moving quote requests.
"""

import os
import sys
import traceback
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import logging
from core.database import db, init_db

# Configure logging to output to stdout as well
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure database connection from environment variables or use default
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Print the database URI for debugging
print(f"Using database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

try:
    # Initialize database
    init_db(app)
    print("Database initialized successfully")
except Exception as e:
    print(f"Error initializing database: {str(e)}")
    traceback.print_exc()
    sys.exit(1)

def fix_permissions():
    """
    Grant necessary permissions to ALL database users for the moving_quote_requests table
    """
    try:
        # Using PUBLIC to grant permissions to all users instead of a specific user
        print("Will grant permissions to PUBLIC (all database users)")
        
        # Use a fresh connection to avoid transaction issues
        with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            print("Checking if table exists...")
            
            # First check if this is PostgreSQL (syntax is PostgreSQL specific)
            try:
                result = connection.execute(text("SELECT version();"))
                db_version = result.scalar()
                print(f"Database version: {db_version}")
                
                if 'postgresql' not in db_version.lower():
                    print("WARNING: This script is designed for PostgreSQL. Your database appears to be different.")
                    print("Permissions might need to be granted differently for your database type.")
            except Exception as e:
                print(f"Error checking database type: {str(e)}")
            
            # Check if the table exists
            try:
                result = connection.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'moving_quote_requests')"))
                table_exists = result.scalar()
                
                if not table_exists:
                    print("ERROR: The moving_quote_requests table does not exist. Please run migrations first.")
                    return
                
                print("Table 'moving_quote_requests' exists. Proceeding with permission grants.")
            except Exception as e:
                print(f"Error checking if table exists: {str(e)}")
                traceback.print_exc()
                return
            
            print("Granting permissions for moving_quote_requests table...")
            
            # Execute GRANT statements directly without explicit transaction
            # since we're using AUTOCOMMIT mode
            try:
                # Grant SELECT, INSERT, UPDATE, DELETE permissions
                print(f"Executing: GRANT SELECT, INSERT, UPDATE, DELETE ON moving_quote_requests TO PUBLIC")
                connection.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON moving_quote_requests TO PUBLIC"))
                
                try:
                    # Check if sequence exists first
                    seq_check = connection.execute(text(
                        "SELECT EXISTS (SELECT FROM information_schema.sequences WHERE sequence_name = 'moving_quote_requests_id_seq')"
                    ))
                    seq_exists = seq_check.scalar()
                    
                    if seq_exists:
                        print(f"Executing: GRANT USAGE, SELECT ON SEQUENCE moving_quote_requests_id_seq TO PUBLIC")
                        # Grant usage and select on the sequences (for ID generation)
                        connection.execute(text(f"GRANT USAGE, SELECT ON SEQUENCE moving_quote_requests_id_seq TO PUBLIC"))
                    else:
                        print("WARNING: Sequence 'moving_quote_requests_id_seq' not found. Skipping sequence permissions.")
                except Exception as e:
                    print(f"Error checking sequence: {str(e)}")
                    # Continue anyway
                
                print("Successfully granted permissions to all database users.")
            except SQLAlchemyError as e:
                print(f"Failed to grant permissions: {str(e)}")
                traceback.print_exc()
                raise
            
            # Verify permissions
            print("Verifying permissions...")
            try:
                # Try to select from the table
                result = connection.execute(text("SELECT COUNT(*) FROM moving_quote_requests"))
                count = result.scalar()
                print(f"Verified SELECT permission. Current record count: {count}")
            except SQLAlchemyError as e:
                print(f"Permission verification failed: {str(e)}")
                traceback.print_exc()
                raise
                
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("Starting permission fix for moving_quote_requests table...")
    with app.app_context():
        fix_permissions()
    print("Permission fix completed.") 