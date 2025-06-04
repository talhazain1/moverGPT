"""
Migration script to create or update the api_keys table.

This script ensures that the api_keys table exists with the correct schema,
particularly making sure it has the 'status' field instead of 'active'.
"""

import logging
from sqlalchemy import text, inspect
from core.database import db

logger = logging.getLogger(__name__)

def run_migration():
    """
    Run the migration to create or update the api_keys table.
    """
    logger.info("Starting api_keys table migration")
    
    try:
        # Check if the api_keys table exists using SQLAlchemy's inspect
        inspector = inspect(db.engine)
        table_exists = 'api_keys' in inspector.get_table_names()
        
        if table_exists:
            logger.info("api_keys table exists")
            
            # Check if the 'status' column exists
            columns = [col['name'] for col in inspector.get_columns('api_keys')]
            status_exists = 'status' in columns
            active_exists = 'active' in columns
            
            if status_exists:
                logger.info("'status' column exists in api_keys table")
            else:
                logger.info("'status' column does not exist in api_keys table")
                # Add 'status' column in a separate transaction
                try:
                    db.session.execute(text("""
                        ALTER TABLE api_keys 
                        ADD COLUMN status VARCHAR(50) DEFAULT 'active'
                    """))
                    db.session.commit()
                    logger.info("Added 'status' column to api_keys table")
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error adding status column: {str(e)}")
                    return False
            
            # If 'active' exists but 'status' also exists, migrate data
            if active_exists and status_exists:
                logger.info("Migrating data from 'active' to 'status' column")
                try:
                    db.session.execute(text("""
                        UPDATE api_keys 
                        SET status = CASE WHEN active = TRUE THEN 'active' ELSE 'inactive' END
                        WHERE status IS NULL
                    """))
                    db.session.commit()
                    logger.info("Data migration from 'active' to 'status' completed")
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error migrating data: {str(e)}")
                    # Continue anyway since this is just a data migration
        else:
            logger.info("api_keys table does not exist")
            # Create the table in a separate transaction
            try:
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        key VARCHAR(255) NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP,
                        status VARCHAR(50) DEFAULT 'active',
                        revoked_at TIMESTAMP,
                        subscription_plan VARCHAR(50) DEFAULT 'basic' NOT NULL,
                        FOREIGN KEY (company_id) REFERENCES users(id)
                    )
                """))
                db.session.commit()
                logger.info("api_keys table created successfully")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating api_keys table: {str(e)}")
                return False
        
        logger.info("api_keys table migration completed successfully")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in api_keys table migration: {str(e)}")
        return False 