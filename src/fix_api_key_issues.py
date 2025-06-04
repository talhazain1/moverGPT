#!/usr/bin/env python3
"""
Fix API Key Issues Script

This script fixes issues with the API key system:
1. Runs migrations to ensure the api_keys table has the correct schema
2. Creates API keys for companies that don't have one
"""

import os
import sys
import logging
from flask import Flask
from core.database import db
from migrations.create_api_keys_table import run_migration
from sqlalchemy import text
import secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create a minimal Flask app for database operations."""
    app = Flask(__name__)
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    db.init_app(app)
    
    return app

def ensure_api_keys_for_companies():
    """Ensure all companies have an API key."""
    logger.info("Ensuring all companies have API keys")
    
    try:
        # Get all company IDs
        company_ids_result = db.session.execute(text("""
            SELECT id FROM users WHERE company_id IS NULL
            UNION
            SELECT DISTINCT company_id FROM users WHERE company_id IS NOT NULL
        """))
        company_ids = [row[0] for row in company_ids_result]
        
        logger.info(f"Found {len(company_ids)} companies")
        
        # For each company, check if they have an API key
        for company_id in company_ids:
            try:
                # Check if company has an API key
                api_key_result = db.session.execute(text("""
                    SELECT key FROM api_keys 
                    WHERE company_id = :company_id AND status = 'active'
                    ORDER BY created_at DESC LIMIT 1
                """), {"company_id": company_id})
                api_key_row = api_key_result.fetchone()
                
                if not api_key_row:
                    # Create a new API key
                    logger.info(f"Creating API key for company ID: {company_id}")
                    api_key = f"sk_{secrets.token_hex(24)}"
                    
                    # Get the company's subscription plan
                    subscription_plan_result = db.session.execute(text("""
                        SELECT subscription_plan FROM users WHERE id = :company_id
                    """), {"company_id": company_id})
                    subscription_plan_row = subscription_plan_result.fetchone()
                    subscription_plan = subscription_plan_row[0] if subscription_plan_row and subscription_plan_row[0] else 'basic'
                    
                    db.session.execute(text("""
                        INSERT INTO api_keys (company_id, key, status, created_at, subscription_plan)
                        VALUES (:company_id, :key, 'active', NOW(), :subscription_plan)
                    """), {
                        "company_id": company_id,
                        "key": api_key,
                        "subscription_plan": subscription_plan
                    })
                    
                    db.session.commit()
                    logger.info(f"Created API key for company ID: {company_id}")
                else:
                    logger.info(f"Company ID {company_id} already has an API key")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error processing company ID {company_id}: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"Error ensuring API keys for companies: {str(e)}")
        return False

def main():
    """Run the fix script."""
    logger.info("Starting API key fix script")
    
    app = create_app()
    with app.app_context():
        # Run migrations first
        logger.info("Running API keys table migration")
        if not run_migration():
            logger.error("API keys table migration failed")
            return False
        
        # Ensure all companies have API keys
        logger.info("Ensuring all companies have API keys")
        if not ensure_api_keys_for_companies():
            logger.error("Failed to ensure API keys for all companies")
            return False
        
        logger.info("API key fix script completed successfully")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 