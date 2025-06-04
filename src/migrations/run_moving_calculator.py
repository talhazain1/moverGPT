"""
Run Moving Calculator Migration

This script executes the SQL migration for adding the moving cost calculator features.
"""

import os
import sys
import psycopg2
from psycopg2 import sql
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get database connection from environment or use default
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb')

def run_migration():
    """
    Run the SQL migration script for moving calculator features.
    """
    try:
        # Read the SQL file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sql_file = os.path.join(script_dir, 'moving_calculator.sql')

        with open(sql_file, 'r') as f:
            sql_commands = f.read()

        # Connect to the database
        logger.info(f"Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        # Execute the SQL commands
        logger.info("Executing migration...")
        cursor.execute(sql_commands)
        
        # Log the result
        logger.info("Migration completed successfully")
        
        # Close the connection
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting moving calculator migration...")
    success = run_migration()
    if success:
        logger.info("Migration completed successfully.")
        sys.exit(0)
    else:
        logger.error("Migration failed.")
        sys.exit(1) 