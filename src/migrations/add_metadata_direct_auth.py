#!/usr/bin/env python
# Direct migration script with hardcoded credentials

import sys
import traceback

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Error: psycopg2 package is required for this script.")
    print("Install it with: pip install psycopg2-binary")
    sys.exit(1)

def main():
    """Main function to run the migration"""
    try:
        print("Starting migration: Add booking_metadata column to moving_bookings table")
        
        # Use the specific credentials provided
        conn_params = {
            'host': 'localhost',
            'port': '5432',
            'dbname': 'chatbotdb',
            'user': 'myuser',
            'password': 'mypassword'  # Make sure to keep this secure
        }
        
        # Connect to the database
        print(f"Connecting to database {conn_params['dbname']} on {conn_params['host']}:{conn_params['port']} as {conn_params['user']}")
        conn = psycopg2.connect(
            host=conn_params['host'],
            port=conn_params['port'],
            dbname=conn_params['dbname'],
            user=conn_params['user'],
            password=conn_params['password']
        )
        
        # Set isolation level to AUTOCOMMIT
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Create a cursor
        cur = conn.cursor()
        
        # Check if the column already exists
        print("Checking if booking_metadata column exists...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'moving_bookings' 
            AND column_name = 'booking_metadata'
        """)
        
        column_exists = cur.fetchone() is not None
        
        if column_exists:
            print("Column booking_metadata already exists, skipping migration.")
        else:
            # Try adding the column to the table
            print("Adding booking_metadata column...")
            try:
                cur.execute("""
                    ALTER TABLE moving_bookings 
                    ADD COLUMN booking_metadata JSONB DEFAULT '{}'::jsonb
                """)
                print("Column added successfully.")
                
                # Set default values for existing records
                print("Setting default values for existing records...")
                cur.execute("""
                    UPDATE moving_bookings 
                    SET booking_metadata = '{}'::jsonb
                """)
                print("Default values set successfully.")
            except psycopg2.errors.InsufficientPrivilege:
                print("Insufficient privileges to alter the table structure.")
                print("Attempting to create a view-based workaround instead...")
                
                # Try to create a view as a workaround
                try:
                    print("Creating a view with the additional column...")
                    cur.execute("DROP VIEW IF EXISTS moving_bookings_with_metadata")
                    cur.execute("""
                        CREATE VIEW moving_bookings_with_metadata AS
                        SELECT *, '{}'::jsonb as booking_metadata
                        FROM moving_bookings
                    """)
                    print("View created successfully.")
                    print("You can now query from moving_bookings_with_metadata instead of moving_bookings")
                    
                    # Test if the view works
                    cur.execute("SELECT COUNT(*) FROM moving_bookings_with_metadata")
                    count = cur.fetchone()[0]
                    print(f"Verified view access: Found {count} booking records")
                    
                except Exception as view_error:
                    print(f"Error creating view: {view_error}")
                    raise
        
        # Close cursor and connection
        cur.close()
        conn.close()
        
        print("Migration completed successfully.")
        return 0
        
    except Exception as e:
        print(f"Error in migration: {e}")
        traceback.print_exc()
        print("Migration failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 