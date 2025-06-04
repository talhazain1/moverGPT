#!/usr/bin/env python3
"""
Setup script to initialize the database with necessary tables and initial data.
This will create all required tables including the moving_parameters table.
"""

import sys
import os
import json
import time
from datetime import datetime

# Add the src directory to the path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    # Import necessary modules
    print("Importing required modules...")
    from src.main import app
    from core.database import db
    from flask_migrate import upgrade, stamp
    from companies.models import Company, MovingParameters
    from sqlalchemy.orm.attributes import flag_modified
    from sqlalchemy import text
    
    print("Starting database setup...")
    
    with app.app_context():
        # Check if moving_parameters table exists
        try:
            print("Checking if moving_parameters table exists...")
            db.session.execute(text("SELECT 1 FROM moving_parameters LIMIT 1"))
            print("✓ moving_parameters table exists")
            moving_parameters_exists = True
        except Exception:
            print("✗ moving_parameters table does not exist - will create it")
            moving_parameters_exists = False
        
        if not moving_parameters_exists:
            print("\nCreating tables...")
            try:
                # If the migrations directory exists, try to run migrations
                if os.path.exists('migrations'):
                    print("Running database migrations...")
                    try:
                        # Try to run migrations
                        upgrade()
                        print("✓ Migrations completed successfully")
                    except Exception as e:
                        print(f"✗ Migration error: {e}")
                        print("Trying to manually create tables...")
                        db.create_all()
                        # Mark as head to avoid future migration errors
                        stamp()
                        print("✓ Tables created and migrations stamped")
                else:
                    # If no migrations directory, just create all tables
                    print("No migrations directory found, creating tables directly...")
                    db.create_all()
                    print("✓ Tables created directly")
                
            except Exception as e:
                print(f"✗ Error creating tables: {e}")
                print("Attempting to create moving_parameters table directly...")
                try:
                    # Try to create only the moving_parameters table
                    sql_create_table = text("""
                    CREATE TABLE IF NOT EXISTS moving_parameters (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        base_rate_per_mile FLOAT DEFAULT 1.5,
                        move_size_rates JSONB DEFAULT '{}',
                        additional_service_costs JSONB DEFAULT '{}',
                        rate_adjustments JSONB DEFAULT '{}',
                        email_config JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
                    )
                    """)
                    db.session.execute(sql_create_table)
                    db.session.commit()
                    print("✓ moving_parameters table created directly with SQL")
                except Exception as e2:
                    print(f"✗ Error creating moving_parameters table: {e2}")
                    sys.exit(1)
        
        # Get all companies
        companies = Company.query.all()
        print(f"\nFound {len(companies)} companies in database")
        
        # Create moving parameters for each company
        for company in companies:
            print(f"\nSetting up moving parameters for company {company.id}: {company.name}")
            
            # Check if moving parameters exist
            params = MovingParameters.query.filter_by(company_id=company.id).first()
            
            if params:
                print(f"Moving parameters found for company {company.id}")
                
                # Check if the fields need updating
                if not params.move_size_rates:
                    print("Updating empty move size rates...")
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
                    
                if not params.additional_service_costs:
                    print("Updating empty additional service costs...")
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
                    flag_modified(params, "additional_service_costs")
                    
                if not params.rate_adjustments:
                    print("Updating empty rate adjustments...")
                    params.rate_adjustments = {
                        "seasonality_rate": 0.10,
                        "rural_location_rate": 0.10,
                        "min_cost_multiplier": 1.1,
                        "max_cost_multiplier": 1.4
                    }
                    flag_modified(params, "rate_adjustments")
                
                db.session.commit()
                print("✓ Updated moving parameters")
                
            else:
                print(f"Creating new moving parameters for company {company.id}")
                try:
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
                    db.session.commit()
                    print(f"✓ Created default parameters for company ID {company.id}")
                except Exception as e:
                    db.session.rollback()
                    print(f"✗ Error creating default parameters: {e}")
        
        # Create debug routes
        @app.route('/api/debug/database-status')
        def debug_database_status():
            from flask import jsonify
            
            # Check all relevant tables
            tables_status = {}
            for table_name in ['companies', 'moving_parameters', 'users', 'api_keys']:
                try:
                    count = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                    tables_status[table_name] = {
                        'exists': True,
                        'count': count
                    }
                except Exception as e:
                    tables_status[table_name] = {
                        'exists': False,
                        'error': str(e)
                    }
            
            return jsonify({
                'status': 'success',
                'database_status': {
                    'tables': tables_status,
                    'timestamp': datetime.now().isoformat()
                }
            })
        
        print("\n✓ Database setup complete!")
        print("\nPlease restart your Flask application to apply these changes.")
        print("Then verify your database status at:")
        print("  https://app.movergpt.com/api/debug/database-status")
        
except ImportError as e:
    print(f"✗ Error importing required modules: {e}")
    print("Make sure you're running this script from the backend directory.")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error setting up database: {e}")
    sys.exit(1) 