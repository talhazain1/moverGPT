#!/usr/bin/env python3
"""
Migration runner script.

This script runs database migrations to ensure the schema is up to date.
"""

import os
import sys
import logging
from flask import Flask
from core.database import db
from migrations.create_api_keys_table import run_migration as run_api_keys_migration
from migrations.add_sender_to_chat_messages import run_migration as run_sender_migration
from migrations.create_company_feature_settings import run_migration as run_company_feature_settings_migration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create a minimal Flask app for migrations."""
    app = Flask(__name__)
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    db.init_app(app)
    
    return app

def run_migrations():
    """Run all database migrations."""
    logger.info("Starting database migrations")
    
    # Create Flask app context
    app = create_app()
    with app.app_context():
        # Run migrations
        api_keys_result = run_api_keys_migration()
        sender_result = run_sender_migration()
        company_features_result = run_company_feature_settings_migration()
        
        # Add more migrations here as needed
        
        # Check results
        if api_keys_result and sender_result and company_features_result:
            logger.info("All migrations completed successfully")
            return True
        else:
            logger.error("Some migrations failed")
            return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1) 