#!/usr/bin/env python3
"""
Test script for cookie authentication issues
"""

import requests
import time
import sys
from pprint import pprint
import jwt
import datetime

# Configuration
BASE_URL = "http://localhost:5006"
DEBUG_PORT = 5007

def test_authentication_flow():
    """Test the complete authentication flow"""
    print("=== Testing Authentication Flow ===")
    
    # First, try the debug endpoint to see cookies
    debug_url = f"http://localhost:{DEBUG_PORT}/debug/session"
    try:
        debug_resp = requests.get(debug_url)
        print(f"Debug response status: {debug_resp.status_code}")
        print("Debug response:")
        pprint(debug_resp.json())
        print(f"Debug cookie: {debug_resp.cookies.get('debug_token')}")
        print()
        
        # Get the test token
        test_token = debug_resp.json().get('test_token')
        
        # Now set the token in a cookie
        set_token_url = f"http://localhost:{DEBUG_PORT}/debug/set_token/{test_token}"
        set_token_resp = requests.get(set_token_url)
        print(f"Set token response status: {set_token_resp.status_code}")
        print(f"Set token cookies: {set_token_resp.cookies}")
        
        # Create a session that maintains cookies
        session = requests.Session()
        
        # Visit the set token page to get the cookie
        session.get(set_token_url)
        
        # Now try to access the debug endpoint again with the cookie
        debug_with_cookie = session.get(debug_url)
        print("Debug with cookie response:")
        pprint(debug_with_cookie.json())
        
        # Try to access the parameters endpoint
        params_url = f"{BASE_URL}/api/companies/debug/moving-parameters/1"
        params_resp = session.get(params_url)
        print(f"Parameters response status: {params_resp.status_code}")
        if params_resp.ok:
            print("Parameters response:")
            pprint(params_resp.json())
        else:
            print(f"Parameters error: {params_resp.text}")
            
    except Exception as e:
        print(f"Error in authentication test: {e}")
        
def generate_test_token():
    """Generate a test JWT token for debugging"""
    secret = "your_secret_key"  # Must match the secret in the app
    payload = {
        'user_id': 23,  # Use a valid user ID from your database
        'company_id': 23,  # Use a valid company ID
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    print(f"Generated test token: {token}")
    return token

if __name__ == "__main__":
    print("Testing cookie-based authentication for moving parameters")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--token":
        generate_test_token()
    else:
        test_authentication_flow() 