"""
Migration script to add MovingQuoteRequest table and enable moving_calculator feature

This script adds the MovingQuoteRequest table to store submissions from the moving cost calculator form
and updates CompanyFeatureSettings to include the moving_calculator feature.
"""

import os
from flask import Flask
from core.database import db, init_db
from companies.models import MovingQuoteRequest, Company, CompanyFeatureSettings
from sqlalchemy import inspect
import logging

app = Flask(__name__)

# Configure database connection
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """
    Add the MovingQuoteRequest table to the database and
    update CompanyFeatureSettings to include moving_calculator feature
    """
    
    with app.app_context():
        # Check if table already exists
        inspector = inspect(db.engine)
        if 'moving_quote_requests' in inspector.get_table_names():
            logger.info("MovingQuoteRequest table already exists. Skipping creation.")
        else:
            # Create the MovingQuoteRequest table
            logger.info("Creating MovingQuoteRequest table...")
            db.create_all()
            
            # Verify the table was created
            inspector = inspect(db.engine)
            if 'moving_quote_requests' in inspector.get_table_names():
                logger.info("MovingQuoteRequest table created successfully!")
            else:
                logger.error("Failed to create MovingQuoteRequest table.")
                return
        
        # Update CompanyFeatureSettings to include moving_calculator feature
        logger.info("Updating CompanyFeatureSettings to include moving_calculator feature...")
        
        # Get all companies with moving in their niche
        moving_companies = Company.query.filter(Company.niche.ilike('%moving%')).all()
        count = 0
        
        for company in moving_companies:
            # Get the company's feature settings
            feature_settings = CompanyFeatureSettings.query.filter_by(company_id=company.id).first()
            
            if feature_settings:
                # Enable moving_calculator feature for moving companies
                if 'moving_calculator' not in feature_settings.enabled_features:
                    feature_settings.enabled_features['moving_calculator'] = True
                    db.session.add(feature_settings)
                    count += 1
        
        if count > 0:
            db.session.commit()
            logger.info(f"Enabled moving_calculator feature for {count} moving companies.")
        else:
            logger.info("No feature settings updated.")

if __name__ == "__main__":
    run_migration()
    logger.info("Migration completed successfully.") 