#!/usr/bin/env python3
"""
Script to set up environment variables for the chatbot platform.
Run this script before starting the server to ensure all required environment variables are set.
"""

import os
import sys

def setup_env():
    """Set up the environment variables needed for the chatbot platform."""
    print("Setting up environment variables for the chatbot platform...")
    
    # Check if OPENAI_API_KEY is already set
    openai_key = os.environ.get('OPENAI_API_KEY')
    if openai_key:
        print("OPENAI_API_KEY is already set.")
    else:
        # Prompt user for API key
        print("\nOpenAI API key is required for the chatbot to function.")
        print("You can get your API key from https://platform.openai.com/api-keys")
        api_key = input("Enter your OpenAI API key: ")
        
        if not api_key.strip():
            print("Error: API key cannot be empty.")
            sys.exit(1)
        
        # Set the environment variable
        os.environ['OPENAI_API_KEY'] = api_key.strip()
        print("OPENAI_API_KEY has been set for this session.")
    
    print("\nEnvironment setup complete. You can now run the server.")
    print("Note: These settings only apply to the current terminal session.")
    print("To make them permanent, add them to your shell profile or use a .env file.")

if __name__ == "__main__":
    setup_env() 