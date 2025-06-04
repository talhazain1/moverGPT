#!/usr/bin/env python3
"""
Debug script for the moving estimate functionality.
This script directly tests the MovingChatHandler to diagnose issues with the moving estimate.
"""

import os
import sys
import json
import logging
from flask import Flask

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_moving_estimate(company_id=23, query=None):
    """Debug the moving estimate functionality by directly testing the MovingChatHandler."""
    
    print("Debugging moving estimate functionality...")
    
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
    
    # Ensure OPENAI_API_KEY is set
    if not os.environ.get('OPENAI_API_KEY'):
        api_key = input("Enter your OpenAI API key: ")
        if api_key.strip():
            os.environ['OPENAI_API_KEY'] = api_key.strip()
            print("OpenAI API key set for this session")
        else:
            print("Warning: No OpenAI API key provided")
    
    # Initialize the database
    try:
        from core.database import db
        db.init_app(app)
    except ImportError:
        print("Error: Could not import core.database. Make sure you're running this script from the correct directory.")
        return False
    
    with app.app_context():
        # Import models and handlers
        try:
            from companies.models import MovingParameters, Company
            from chatbot.moving_chat_handler import MovingChatHandler
        except ImportError as e:
            print(f"Error importing required modules: {e}")
            print("Make sure you're running this script from the project root directory.")
            return False
        
        # Check if the company exists
        company = Company.query.get(company_id)
        if not company:
            print(f"Error: Company with id={company_id} not found.")
            return False
        
        # Check if MovingParameters exist
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        if not params:
            print(f"Error: No MovingParameters found for company_id={company_id}.")
            print("Run setup_moving_params.py to create them.")
            return False
        
        print("\nMovingParameters found:")
        print(f"- move_size_rates: {json.dumps(params.move_size_rates, indent=2)}")
        print(f"- base_rate_per_mile: {params.base_rate_per_mile}")
        
        # Create a test session ID
        test_session_id = 999999
        
        # Create a MovingChatHandler instance
        handler = MovingChatHandler(company_id, test_session_id)
        
        # Use the provided query or a default one
        if not query:
            query = "I want to move from New York to Boston, a 2 bedroom apartment on 1st september 2025"
        
        print(f"\nTesting query: {query}")
        
        # Process the message
        response_data = handler.handle_message(query)
        
        print("\nHandler state after processing:")
        print(f"- State: {handler.state.name}")
        print(f"- Collected info: {json.dumps(handler.collected_info, indent=2)}")
        
        # Check if we have all required information
        if handler.collected_info.get('is_complete'):
            print("\nAll required information collected.")
        else:
            print("\nMissing information:")
            for field in ['origin', 'destination', 'move_size', 'move_date']:
                if not handler.collected_info.get(field):
                    print(f"- {field}")
        
        # If we're still in COLLECTING_INFO state, try to manually complete the information
        if handler.state.name == 'COLLECTING_INFO' and not handler.collected_info.get('is_complete'):
            print("\nManually completing missing information...")
            
            if not handler.collected_info.get('origin'):
                handler.collected_info['origin'] = 'New York'
                print("- Set origin to 'New York'")
            
            if not handler.collected_info.get('destination'):
                handler.collected_info['destination'] = 'Boston'
                print("- Set destination to 'Boston'")
            
            if not handler.collected_info.get('move_size'):
                handler.collected_info['move_size'] = '2-bedroom'
                print("- Set move_size to '2-bedroom'")
            
            if not handler.collected_info.get('move_date'):
                handler.collected_info['move_date'] = '2025-09-01'
                print("- Set move_date to '2025-09-01'")
            
            handler.collected_info['is_complete'] = True
            
            # Now try to calculate the estimate
            print("\nCalculating estimate with manually completed information...")
            response_data = handler._calculate_and_return_estimate()
        
        # Check the response
        print("\nResponse:")
        if response_data:
            print(f"- Response text: {response_data.get('response')}")
            print(f"- State: {response_data.get('state')}")
            
            if 'estimate' in response_data:
                print(f"- Estimate: {json.dumps(response_data.get('estimate'), indent=2)}")
            else:
                print("- No estimate in response")
                
                if 'error' in response_data:
                    print(f"- Error: {response_data.get('error')}")
        else:
            print("No response data returned")
        
        return True

if __name__ == "__main__":
    # Get company ID from command line if provided
    company_id = 23  # Default company ID
    query = None
    
    if len(sys.argv) > 1:
        try:
            company_id = int(sys.argv[1])
        except ValueError:
            query = sys.argv[1]
    
    if len(sys.argv) > 2:
        query = sys.argv[2]
    
    debug_moving_estimate(company_id, query) 