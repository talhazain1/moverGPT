#!/usr/bin/env python
# Direct migration script to add booking_metadata column using psycopg2 (no Flask/SQLAlchemy dependency)

import os
import sys
import traceback
import getpass

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Error: psycopg2 package is required for this script.")
    print("Install it with: pip install psycopg2-binary")
    sys.exit(1)

def get_db_connection_params():
    """Get database connection parameters from various sources"""
    
    db_url = None
    
    # Try environment variables first
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    
    # If not found, try reading from .env file
    if not db_url and os.path.exists('.env'):
        with open('.env', 'r') as env_file:
            for line in env_file:
                if line.strip().startswith('DATABASE_URL='):
                    db_url = line.strip().split('=', 1)[1].strip('\'"')
                    break
                elif line.strip().startswith('SQLALCHEMY_DATABASE_URI='):
                    db_url = line.strip().split('=', 1)[1].strip('\'"')
                    break
    
    # If still not found, ask the user
    if not db_url:
        print("Database connection string not found in environment variables or .env file.")
        use_defaults = input("Do you want to use default connection parameters? (y/n): ").lower() == 'y'
        
        if use_defaults:
            host = 'localhost'
            port = '5432'
            dbname = input("Database name [postgres]: ") or 'postgres'
            user = input("Database user [postgres]: ") or 'postgres'
            password = getpass.getpass("Database password: ")
            
            return {
                'host': host,
                'port': port,
                'dbname': dbname,
                'user': user,
                'password': password
            }
        else:
            # Ask for full connection string
            db_url = input("Enter database connection string (e.g., postgresql://user:pass@localhost/dbname): ")
    
    # If we have a URL, parse it
    if db_url:
        if db_url.startswith('postgresql://') or db_url.startswith('postgres://'):
            # Parse the URL to get connection parameters
            # Format: postgresql://username:password@hostname:port/database
            db_url = db_url.replace('postgresql://', '').replace('postgres://', '')
            
            auth_host, db = db_url.split('/', 1) if '/' in db_url else (db_url, '')
            
            if '@' in auth_host:
                auth, host = auth_host.split('@', 1)
            else:
                auth, host = '', auth_host
                
            if ':' in auth:
                user, password = auth.split(':', 1)
            else:
                user, password = auth, ''
                
            if ':' in host:
                host, port = host.split(':', 1)
            else:
                port = '5432'
                
            return {
                'host': host,
                'port': port,
                'dbname': db,
                'user': user,
                'password': password
            }
        else:
            print("Error: Unsupported database URL format.")
            sys.exit(1)
    
    # If we get here, we couldn't get connection parameters
    print("Error: Could not determine database connection parameters.")
    sys.exit(1)

def main():
    """Main function to run the migration"""
    try:
        print("Starting migration: Add booking_metadata column to moving_bookings table")
        
        # Get connection parameters
        conn_params = get_db_connection_params()
        
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
            # Add the column to the table
            print("Adding booking_metadata column...")
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