"""
Migration script to create the company_feature_settings table.
"""

import logging
from sqlalchemy import text, inspect
from core.database import db

logger = logging.getLogger(__name__)

def run_migration():
    """
    Run the migration to create the company_feature_settings table.
    """
    logger.info("Starting company_feature_settings table migration")

    try:
        inspector = inspect(db.engine)
        table_exists = 'company_feature_settings' in inspector.get_table_names()

        if table_exists:
            logger.info("company_feature_settings table exists")
        else:
            logger.info("company_feature_settings table does not exist")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS company_feature_settings (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    enabled_features JSONB DEFAULT '{}'::jsonb,
                    feature_limits JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                )
            """))
            db.session.commit()
            logger.info("company_feature_settings table created successfully")

        logger.info("company_feature_settings table migration completed successfully")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in company_feature_settings table migration: {str(e)}")
        return False 