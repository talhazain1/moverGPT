#!/usr/bin/env python3
"""
Test script for the moving estimate functionality.
This script sends a request to the chatbot API to test the moving estimate feature.
"""

import requests
import json
import sys

def test_moving_estimate(api_url="http://localhost:5006/api/chatbot/inference", company_id=23):
    """
    Test the moving estimate functionality by sending a request to the API.
    
    Args:
        api_url (str): The URL of the chatbot inference API
        company_id (int): The ID of the company to use for the test
    """
    print("Testing moving estimate functionality...")
    
    # Create a session
    session_response = requests.post(
        "http://localhost:5006/api/chatbot/session",
        json={"company_id": company_id}
    )
    
    if session_response.status_code != 201:
        print(f"Error creating session: {session_response.text}")
        return
    
    session_data = session_response.json()
    session_id = session_data.get("session_id")
    
    if not session_id:
        print("No session ID returned")
        return
    
    print(f"Created session with ID: {session_id}")
    
    # Test moving query
    query = "I want to move from New York to Boston, a 2 bedroom apartment on 1st september 2025"
    
    response = requests.post(
        api_url,
        json={
            "company_id": company_id,
            "query": query,
            "session_id": session_id
        }
    )
    
    print("\nRequest:")
    print(f"URL: {api_url}")
    print(f"Payload: {json.dumps({'company_id': company_id, 'query': query, 'session_id': session_id}, indent=2)}")
    
    print("\nResponse:")
    print(f"Status code: {response.status_code}")
    
    try:
        response_data = response.json()
        print(f"Response data: {json.dumps(response_data, indent=2)}")
        
        if response_data.get("status") == "success":
            print("\nSuccess! The chatbot responded with:")
            print(response_data.get("response"))
        else:
            print("\nError in response:")
            print(response_data.get("message"))
    except json.JSONDecodeError:
        print("Error parsing response as JSON")
        print(f"Raw response: {response.text}")

if __name__ == "__main__":
    # Get company ID from command line if provided
    company_id = 23  # Default company ID
    if len(sys.argv) > 1:
        try:
            company_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid company ID: {sys.argv[1]}")
            sys.exit(1)
    
    test_moving_estimate(company_id=company_id) 