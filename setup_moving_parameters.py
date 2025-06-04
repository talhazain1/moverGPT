"""
Set up moving_parameters table with default values.

This script creates the moving_parameters table if it doesn't exist
and populates it with default values for each company.
"""

import os
import sys
import argparse

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from core.database import db
from sqlalchemy import text

def create_tables():
    """Create the moving_parameters table."""
    try:
        print("Creating database tables...")
        
        # Import the models to register them with SQLAlchemy
        from companies.models import MovingParameters
        
        # Create the moving_parameters table
        db.create_all()
        
        print("Tables created successfully!")
        return True
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        return False

def get_all_companies():
    """Get all companies from the database."""
    try:
        from companies.models import Company
        
        companies = Company.query.all()
        print(f"Found {len(companies)} companies")
        return companies
    except Exception as e:
        print(f"Error fetching companies: {str(e)}")
        return []

def setup_default_parameters():
    """Set up default moving parameters for all companies."""
    try:
        print("Setting up default moving parameters for all companies...")
        
        from companies.models import MovingParameters
        
        # Get all companies
        companies = get_all_companies()
        
        for company in companies:
            # Check if parameters already exist
            existing_params = MovingParameters.query.filter_by(company_id=company.id).first()
            
            if existing_params:
                print(f"Parameters already exist for company {company.id} ({company.name})")
                continue
            
            print(f"Creating default parameters for company {company.id} ({company.name})")
            
            # Create new parameters
            params = MovingParameters(company_id=company.id)
            
            # Set default values explicitly
            params.base_rate_per_mile = 1.50
            params.move_size_rates = {
                "studio": 320,
                "1-bedroom": 640, 
                "2-bedroom": 960,
                "3-bedroom": 1280,
                "4-bedroom": 1600,
                "office": 2000,
                "car": 120
            }
            params.additional_service_costs = {
                "packing": {
                    "studio": 100,
                    "1-bedroom": 150,
                    "2-bedroom": 200,
                    "3-bedroom": 250,
                    "4-bedroom": 300,
                    "office": 350,
                    "car": 50
                },
                "storage": {
                    "studio": 80,
                    "1-bedroom": 130,
                    "2-bedroom": 180,
                    "3-bedroom": 230,
                    "4-bedroom": 280,
                    "office": 300,
                    "car": 50
                }
            }
            params.rate_adjustments = {
                "seasonality_rate": 0.10,
                "rural_location_rate": 0.10,
                "min_cost_multiplier": 1.1,
                "max_cost_multiplier": 1.4
            }
            params.email_config = {
                "staff_email": "staff@example.com",
                "staff_subject": "New Booking Confirmed - Action Required",
                "customer_template": "Dear {username},\n\nYour booking has been confirmed with the following details:\n  • From: {origin}\n  • To: {destination}\n  • Move Size: {move_size}\n  • Move Date: {move_date}\n  • Additional Services: {additional_services}\n  • Estimated Cost: ${estimated_cost_min} - ${estimated_cost_max}\n  • Contact No: {contact_no}\n\nThank you for choosing our service. We look forward to serving you!\n\nBest regards,\nThe Moving Team",
                "staff_template": "A new booking has been confirmed with the following details:\n\nCustomer Name: {username}\nEmail: {email}\nContact No: {contact_no}\nFrom: {origin}\nTo: {destination}\nMove Size: {move_size}\nMove Date: {move_date}\nAdditional Services: {additional_services}\nEstimated Cost: ${estimated_cost_min} - ${estimated_cost_max}\n\nPlease proceed with the necessary actions for this booking.\n\nRegards,"
            }
            
            # Add to session
            db.session.add(params)
        
        # Commit all changes
        db.session.commit()
        
        print("Default parameters set up successfully!")
        return True
    except Exception as e:
        print(f"Error setting up default parameters: {str(e)}")
        db.session.rollback()
        return False

def fix_permissions():
    """Fix permissions for the moving_parameters table."""
    try:
        print("Fixing permissions for moving_parameters table...")
        
        # Get database info from the connection
        conn = db.engine.connect()
        
        # Grant permissions to the moving_parameters table
        conn.execute(text("GRANT ALL PRIVILEGES ON TABLE moving_parameters TO current_user"))
        
        # Grant permissions to the moving_parameters_id_seq sequence if it exists
        conn.execute(text("GRANT ALL PRIVILEGES ON SEQUENCE moving_parameters_id_seq TO current_user"))
        
        conn.commit()
        conn.close()
        
        print("Permissions fixed successfully!")
        return True
    except Exception as e:
        print(f"Error fixing permissions: {str(e)}")
        return False

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Set up moving_parameters table with default values")
    parser.add_argument('--create-only', action='store_true', help='Only create tables without adding default values')
    parser.add_argument('--defaults-only', action='store_true', help='Only add default values without creating tables')
    parser.add_argument('--fix-permissions', action='store_true', help='Fix permissions on the moving_parameters table')
    parser.add_argument('--company-id', type=int, help='Set up parameters for a specific company ID')
    
    args = parser.parse_args()
    
    if args.create_only:
        create_tables()
    elif args.defaults_only:
        setup_default_parameters()
    elif args.fix_permissions:
        fix_permissions()
    else:
        # Run all steps
        created = create_tables()
        if created:
            setup_default_parameters()
            fix_permissions()

if __name__ == "__main__":
    # Import the Flask app to initialize database connection
    from main import app
    
    with app.app_context():
        main() 