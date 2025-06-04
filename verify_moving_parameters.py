#!/usr/bin/env python3
"""
This script verifies and fixes moving parameters in the database.
It ensures that moving parameters exist for all companies and outputs debug information.
"""

import sys
import os
import json
from datetime import datetime

# Add the src directory to the path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    # Import necessary modules
    from src.main import app
    from companies.models import Company, MovingParameters
    from core.database import db
    from sqlalchemy.orm.attributes import flag_modified
    
    # Get all companies
    with app.app_context():
        # Get list of all companies
        companies = Company.query.all()
        print(f"Found {len(companies)} companies in database")
        
        # Check moving parameters for each company
        for company in companies:
            print(f"\nChecking company {company.id}: {company.name}")
            
            # Check if moving parameters exist
            params = MovingParameters.query.filter_by(company_id=company.id).first()
            
            if params:
                print(f"Moving parameters found for company {company.id}")
                print(f"- Base rate per mile: {params.base_rate_per_mile}")
                print(f"- Move size rates: {json.dumps(params.move_size_rates, indent=2) if params.move_size_rates else 'None'}")
                if not params.move_size_rates:
                    print("WARNING: Move size rates are empty or null - fixing...")
                    params.move_size_rates = {
                        "studio": 320,
                        "1-bedroom": 640, 
                        "2-bedroom": 960,
                        "3-bedroom": 1280,
                        "4-bedroom": 1600,
                        "office": 2000,
                        "car": 120
                    }
                    flag_modified(params, "move_size_rates")
                    db.session.commit()
                    print("Fixed move size rates")
            else:
                print(f"No moving parameters found for company {company.id} - creating default parameters")
                params = MovingParameters(company_id=company.id)
                
                # Set default values
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
                
                # Mark fields as modified because they're JSON types
                flag_modified(params, "move_size_rates")
                flag_modified(params, "additional_service_costs")
                flag_modified(params, "rate_adjustments")
                
                db.session.add(params)
                try:
                    db.session.commit()
                    print(f"Created default parameters for company ID {company.id}")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error creating default parameters: {e}")
                    
        # Record verification timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("logs/moving_parameters_check.log", "a") as f:
            f.write(f"[{timestamp}] Verified moving parameters for {len(companies)} companies\n")
            
        # Create special debug endpoint
        @app.route('/api/debug/moving-parameter-routes')
        def debug_moving_parameter_routes():
            from flask import jsonify
            routes = []
            for rule in app.url_map.iter_rules():
                if 'moving' in rule.rule:
                    routes.append({
                        'endpoint': rule.endpoint,
                        'rule': rule.rule,
                        'methods': list(rule.methods)
                    })
            return jsonify({
                'status': 'success',
                'routes': routes,
                'verification_time': timestamp
            })
        
        print("\nVerification complete!")
        print("\nNow restart your Flask application to apply these changes.")
        print("\nAfter restarting, test with:")
        print("  https://app.movergpt.com/api/debug/moving-parameter-routes")
        
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this script from the backend directory.")
    sys.exit(1)
except Exception as e:
    print(f"Error verifying moving parameters: {e}")
    sys.exit(1) 