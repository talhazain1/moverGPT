"""
Fix database permissions for moving_parameters table.

This script grants the necessary permissions to access the moving_parameters table.
Run this script with admin database privileges.
"""

import os
import sys
import argparse

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from core.database import db
from sqlalchemy import text

def fix_permissions():
    """Fix permissions for the moving_parameters table."""
    try:
        print("Starting permission fix for moving_parameters table...")
        
        # Get database info from the connection
        conn = db.engine.connect()
        
        # Grant permissions to the moving_parameters table
        conn.execute(text("GRANT ALL PRIVILEGES ON TABLE moving_parameters TO current_user"))
        
        # Grant permissions to the moving_parameters_id_seq sequence if it exists
        conn.execute(text("GRANT ALL PRIVILEGES ON SEQUENCE moving_parameters_id_seq TO current_user"))
        
        conn.commit()
        conn.close()
        
        print("Permissions successfully updated.")
        return True
    except Exception as e:
        print(f"Error fixing permissions: {str(e)}")
        return False

def check_table_exists():
    """Check if the moving_parameters table exists."""
    try:
        conn = db.engine.connect()
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'moving_parameters')"
        ))
        exists = result.scalar()
        conn.close()
        
        if exists:
            print("Table moving_parameters exists.")
        else:
            print("Table moving_parameters does not exist!")
        
        return exists
    except Exception as e:
        print(f"Error checking if table exists: {str(e)}")
        return False

def setup_database():
    """Create the moving_parameters table if it doesn't exist."""
    try:
        print("Setting up moving_parameters table...")
        
        # Import the models to register them with SQLAlchemy
        from companies.models import MovingParameters
        
        # Create all tables
        db.create_all()
        
        print("Database tables created successfully.")
        return True
    except Exception as e:
        print(f"Error setting up database: {str(e)}")
        return False

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Fix permissions for moving_parameters table")
    parser.add_argument('--check-only', action='store_true', help='Only check if the table exists')
    parser.add_argument('--setup-db', action='store_true', help='Create the table if it does not exist')
    
    args = parser.parse_args()
    
    if args.check_only:
        check_table_exists()
    elif args.setup_db:
        exists = check_table_exists()
        if not exists:
            setup_database()
        
        # Fix permissions after setup
        fix_permissions()
    else:
        exists = check_table_exists()
        if exists:
            fix_permissions()
        else:
            print("Table doesn't exist. Run with --setup-db to create it.")

if __name__ == "__main__":
    # Import the Flask app to initialize database connection
    from main import app
    
    with app.app_context():
        main() 