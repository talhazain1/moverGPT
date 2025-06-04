#!/usr/bin/env python3
"""
Script to set up MovingParameters for a company.
This is needed for the moving estimate functionality to work properly.
"""

import os
import sys
import json
from flask import Flask

def setup_moving_params(company_id=23):
    """Set up MovingParameters for the specified company."""
    
    print(f"Setting up MovingParameters for company_id={company_id}...")
    
    # Create a minimal Flask app to access the database
    app = Flask(__name__)
    
    # Import config
    try:
        from config import Config
        app.config.from_object(Config)
        print("Successfully loaded config from config.py")
    except ImportError:
        print("Warning: Could not import config.Config, using default configuration")
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database
    try:
        from core.database import db
        db.init_app(app)
    except ImportError:
        print("Error: Could not import core.database. Make sure you're running this script from the correct directory.")
        return False
    
    with app.app_context():
        # Import models
        try:
            from companies.models import MovingParameters, Company
        except ImportError as e:
            print(f"Error importing required modules: {e}")
            print("Make sure you're running this script from the project root directory.")
            return False
        
        # Check if the company exists
        company = Company.query.get(company_id)
        if not company:
            print(f"Error: Company with id={company_id} not found.")
            return False
        
        # Check if MovingParameters already exist
        existing_params = MovingParameters.query.filter_by(company_id=company_id).first()
        if existing_params:
            print(f"MovingParameters already exist for company_id={company_id}.")
            print("Current parameters:")
            print(f"- move_size_rates: {json.dumps(existing_params.move_size_rates, indent=2)}")
            print(f"- base_rate_per_mile: {existing_params.base_rate_per_mile}")
            
            update = input("Do you want to update these parameters? (y/n): ").lower()
            if update != 'y':
                print("Keeping existing parameters.")
                return True
            
            # Update existing parameters
            existing_params.move_size_rates = {
                "studio": 500,
                "1-bedroom": 700,
                "2-bedroom": 900,
                "3-bedroom": 1200,
                "4-bedroom": 1500
            }
            existing_params.base_rate_per_mile = 2.5
            existing_params.additional_service_costs = {
                "packing": {
                    "studio": 200,
                    "1-bedroom": 300,
                    "2-bedroom": 400,
                    "3-bedroom": 500,
                    "4-bedroom": 600
                },
                "storage": {
                    "studio": 100,
                    "1-bedroom": 150,
                    "2-bedroom": 200,
                    "3-bedroom": 250,
                    "4-bedroom": 300
                }
            }
            existing_params.rate_adjustments = {
                "rural_location_rate": 0.1,
                "seasonality_rate": 0.15,
                "max_cost_multiplier": 1.2
            }
            
            try:
                db.session.commit()
                print("Successfully updated MovingParameters.")
                return True
            except Exception as e:
                db.session.rollback()
                print(f"Error updating MovingParameters: {e}")
                return False
        
        # Create new parameters
        new_params = MovingParameters(
            company_id=company_id,
            move_size_rates={
                "studio": 500,
                "1-bedroom": 700,
                "2-bedroom": 900,
                "3-bedroom": 1200,
                "4-bedroom": 1500
            },
            base_rate_per_mile=2.5,
            additional_service_costs={
                "packing": {
                    "studio": 200,
                    "1-bedroom": 300,
                    "2-bedroom": 400,
                    "3-bedroom": 500,
                    "4-bedroom": 600
                },
                "storage": {
                    "studio": 100,
                    "1-bedroom": 150,
                    "2-bedroom": 200,
                    "3-bedroom": 250,
                    "4-bedroom": 300
                }
            },
            rate_adjustments={
                "rural_location_rate": 0.1,
                "seasonality_rate": 0.15,
                "max_cost_multiplier": 1.2
            }
        )
        
        try:
            db.session.add(new_params)
            db.session.commit()
            print("Successfully created MovingParameters.")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error creating MovingParameters: {e}")
            return False

if __name__ == "__main__":
    # Get company ID from command line if provided
    company_id = 23  # Default company ID
    if len(sys.argv) > 1:
        try:
            company_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid company ID: {sys.argv[1]}")
            sys.exit(1)
    
    success = setup_moving_params(company_id)
    if success:
        print("\nMovingParameters setup complete. You should now be able to get moving estimates.")
    else:
        print("\nFailed to set up MovingParameters. Please check the error messages above.") 