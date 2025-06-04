#!/usr/bin/env python3
"""
Wrapper script to set environment variables and run the server.
"""

import os
import sys
import subprocess
import dotenv

def run_server():
    """Set up environment variables and run the server."""
    print("Starting chatbot platform server...")
    
    # First try to load from .env file if it exists
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        print(f"Loading environment variables from {env_file}")
        dotenv.load_dotenv(env_file)
    
    # Check if OPENAI_API_KEY is set
    openai_key = os.environ.get('OPENAI_API_KEY')
    if not openai_key:
        print("\nOpenAI API key is required for the chatbot to function.")
        print("You can get your API key from https://platform.openai.com/api-keys")
        api_key = input("Enter your OpenAI API key: ")
        
        if not api_key.strip():
            print("Error: API key cannot be empty.")
            sys.exit(1)
        
        # Set the environment variable
        os.environ['OPENAI_API_KEY'] = api_key.strip()
        print("OPENAI_API_KEY has been set for this session.")
        
        # Optionally save to .env file
        save_to_env = input("Save API key to .env file for future use? (y/n): ").lower()
        if save_to_env == 'y':
            try:
                with open(env_file, 'a+') as f:
                    f.seek(0)
                    content = f.read()
                    if 'OPENAI_API_KEY' not in content:
                        if content and not content.endswith('\n'):
                            f.write('\n')
                        f.write(f"OPENAI_API_KEY={api_key.strip()}\n")
                print(f"API key saved to {env_file}")
            except Exception as e:
                print(f"Error saving to .env file: {e}")
    
    # Run the server directly using the main.py in src directory
    print("\nStarting the server...")
    try:
        # Use the absolute path to main.py
        main_file = os.path.join(os.path.dirname(__file__), "src", "main.py")
        
        if not os.path.exists(main_file):
            print(f"Error: main.py not found at {main_file}")
            sys.exit(1)
            
        subprocess.run([sys.executable, main_file], check=True)
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"\nServer exited with error code {e.returncode}")
    except Exception as e:
        print(f"\nError running server: {e}")

if __name__ == "__main__":
    run_server() 