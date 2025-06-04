"""
Migration script to add MovingParameters table

This script adds the MovingParameters table to support the moving company specific features.
"""

import os
from flask import Flask
from core.database import db, init_db
from companies.models import MovingParameters, Company
from sqlalchemy import inspect

app = Flask(__name__)

# Configure database connection
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

def run_migration():
    """Add the MovingParameters table to the database"""
    
    with app.app_context():
        # Check if table already exists
        inspector = inspect(db.engine)
        if 'moving_parameters' in inspector.get_table_names():
            print("MovingParameters table already exists. Skipping creation.")
            return
        
        # Create the MovingParameters table
        print("Creating MovingParameters table...")
        db.create_all()
        
        # Verify the table was created
        inspector = inspect(db.engine)
        if 'moving_parameters' in inspector.get_table_names():
            print("MovingParameters table created successfully!")
        else:
            print("Failed to create MovingParameters table.")
            return
        
        # Add defaults for existing companies with 'moving' in their niche
        print("Adding default moving parameters for moving companies...")
        moving_companies = Company.query.filter(Company.niche.ilike('%moving%')).all()
        count = 0
        
        for company in moving_companies:
            # Check if company already has parameters
            if MovingParameters.query.filter_by(company_id=company.id).first():
                continue
            
            # Create new parameters for company
            params = MovingParameters(company_id=company.id)
            db.session.add(params)
            count += 1
        
        if count > 0:
            db.session.commit()
            print(f"Added default parameters for {count} moving companies.")
        else:
            print("No moving companies found or all already have parameters.")

if __name__ == "__main__":
    run_migration()
    print("Migration completed successfully.") 