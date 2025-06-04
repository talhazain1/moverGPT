import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os

def add_remarks_column():
    try:
        # Connect to the database using the same credentials as the app
        conn = psycopg2.connect(
            dbname='chatbotdb',
            user='user',
            password='',
            host='localhost',
            port='5432'
        )
        
        # Set isolation level to AUTOCOMMIT
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Create a cursor
        cur = conn.cursor()
        
        # Add remarks column if it doesn't exist
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name='support_tickets' 
                    AND column_name='remarks'
                ) THEN
                    ALTER TABLE support_tickets ADD COLUMN remarks TEXT;
                END IF;
            END $$;
        """)
        
        print("Successfully added remarks column to support_tickets table")
        
        # Close cursor and connection
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error adding remarks column: {str(e)}")
        raise

if __name__ == "__main__":
    add_remarks_column() 