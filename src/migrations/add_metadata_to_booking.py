#!/usr/bin/env python
# Migration script to add booking_metadata column to moving_bookings table

import sys
import os
import json
import traceback

# Add the src directory to the path for imports
sys.path.append('src')

try:
    from core.database import db
    from flask import Flask
    import importlib.util
    
    # Try to load config from the main application
    try:
        # First try to import the config module
        from config import Config as AppConfig
        print("Using application config from config module")
        database_uri = AppConfig.SQLALCHEMY_DATABASE_URI
    except ImportError:
        # If that fails, try to find config.py in the project
        print("Config module not found, trying to locate config.py")
        config_path = None
        search_paths = ['src/config.py', 'config.py', 'src/core/config.py']
        
        for path in search_paths:
            if os.path.exists(path):
                config_path = path
                break
                
        if config_path:
            print(f"Found config at {config_path}")
            spec = importlib.util.spec_from_file_location("config", config_path)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            
            # Try to get database URI from the loaded module
            if hasattr(config_module, 'Config') and hasattr(config_module.Config, 'SQLALCHEMY_DATABASE_URI'):
                database_uri = config_module.Config.SQLALCHEMY_DATABASE_URI
            else:
                # Look for database URI in any class in the module
                for attr_name in dir(config_module):
                    attr = getattr(config_module, attr_name)
                    if isinstance(attr, type) and hasattr(attr, 'SQLALCHEMY_DATABASE_URI'):
                        database_uri = attr.SQLALCHEMY_DATABASE_URI
                        break
        
        # If still no database URI, try environment variables
        if not config_path or 'database_uri' not in locals():
            print("Config file not found, using environment variables")
            database_uri = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    
    # If we still don't have a database URI, try some common defaults
    if 'database_uri' not in locals() or not database_uri:
        # Check common locations for database configuration
        if os.path.exists('.env'):
            with open('.env', 'r') as env_file:
                for line in env_file:
                    if line.strip().startswith('DATABASE_URL='):
                        database_uri = line.strip().split('=', 1)[1].strip('\'"')
                        print(f"Found DATABASE_URL in .env file")
                        break
                    elif line.strip().startswith('SQLALCHEMY_DATABASE_URI='):
                        database_uri = line.strip().split('=', 1)[1].strip('\'"')
                        print(f"Found SQLALCHEMY_DATABASE_URI in .env file")
                        break
    
    # If we still don't have a database URI, prompt the user
    if 'database_uri' not in locals() or not database_uri:
        print("Database URI not found in config or environment")
        database_uri = input("Please enter your database connection URI: ")
    
    print(f"Using database URI: {database_uri[:15]}{'...' if len(database_uri) > 15 else ''}")
    
    # Create a minimal Flask app for the migration
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    print("Starting migration: Add booking_metadata column to moving_bookings table")
    
    with app.app_context():
        # Check if the column already exists
        try:
            exists = db.engine.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'moving_bookings' AND column_name = 'booking_metadata'"
            ).fetchone()
            
            if exists:
                print("Column booking_metadata already exists, skipping migration.")
            else:
                # Add the column to the table
                print("Adding booking_metadata column...")
                db.engine.execute(
                    "ALTER TABLE moving_bookings "
                    "ADD COLUMN booking_metadata JSONB DEFAULT '{}'::jsonb"
                )
                print("Column added successfully.")
                
                # Set default values for existing records
                print("Setting default values for existing records...")
                db.engine.execute(
                    "UPDATE moving_bookings "
                    "SET booking_metadata = '{}'::jsonb"
                )
                print("Default values set successfully.")
        
        except Exception as e:
            print(f"Error checking column existence: {e}")
            traceback.print_exc()
            print("Migration failed.")
            sys.exit(1)
            
    print("Migration completed successfully.")
except Exception as e:
    print(f"Error in migration: {e}")
    traceback.print_exc()
    print("Migration failed.")
    sys.exit(1) 