"""
Migration script to add recipient_email column to moving_quote_requests table.
"""

import os
import sys
from flask import Flask
from sqlalchemy import text
import logging

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import db, init_db

app = Flask(__name__)

# Configure database connection with provided credentials
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://movergptuser:M0v3rGPT_2025!@localhost:5432/movergptdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add recipient_email column to moving_quote_requests table"""
    try:
        with app.app_context():
            logger.info("Starting migration: Adding recipient_email column to moving_quote_requests table")
            
            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('moving_quote_requests')
            
            if any(column['name'] == 'recipient_email' for column in columns):
                logger.info("Column 'recipient_email' already exists in moving_quote_requests table. Skipping.")
            else:
                # Add the column
                db.session.execute(text(
                    "ALTER TABLE moving_quote_requests ADD COLUMN recipient_email VARCHAR(120);"
                ))
                db.session.commit()
                logger.info("Successfully added recipient_email column to moving_quote_requests table")
                
            logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        if 'db' in locals() and 'session' in dir(db):
            db.session.rollback()

if __name__ == "__main__":
    with app.app_context():
        run_migration() 