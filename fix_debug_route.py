#!/usr/bin/env python3
"""
Debug script to add a test route to verify Flask routing is working correctly.
"""

import sys
import os

# Add the src directory to the path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    # Import the Flask app
    from src.main import app
    from flask import jsonify
    
    print("Adding debug test route...")
    
    # Add a simple test route that should always work
    @app.route('/api/debug/test', methods=['GET'])
    def debug_test_route():
        return jsonify({
            "status": "success",
            "message": "Debug route is working!",
            "routes_count": len(list(app.url_map.iter_rules()))
        })
    
    # Add a specific test route for the moving parameters endpoint
    @app.route('/api/debug/moving-parameters/<int:company_id>', methods=['GET'])
    def debug_moving_params(company_id):
        return jsonify({
            "status": "success",
            "message": f"Debug route for moving parameters is working for company {company_id}!",
            "test_data": {
                "base_rate_per_mile": 1.5,
                "move_size_rates": {
                    "studio": 320,
                    "1-bedroom": 640
                }
            }
        })
    
    print("Debug routes added successfully!")
    print("Current routes:")
    for rule in app.url_map.iter_rules():
        if 'debug' in rule.rule:
            print(f"{rule.endpoint}: {rule.rule} {rule.methods}")
    
    print("\nNow restart your Flask application to apply these changes.")
    print("\nAfter restarting, test with:")
    print("  https://app.movergpt.com/api/debug/test")
    print("  https://app.movergpt.com/api/debug/moving-parameters/7")
    
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this script from the backend directory.")
    sys.exit(1)
except Exception as e:
    print(f"Error adding routes: {e}")
    sys.exit(1) 