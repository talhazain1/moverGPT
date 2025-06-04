"""
Fix token-related issues with the moving parameters page.

This script creates a JWT token that can be used for testing.
"""

import jwt
import datetime
import argparse
import os
import sys

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

def generate_token(user_id, company_id, secret_key="default_secret"):
    """
    Generate a valid JWT token for testing
    
    Args:
        user_id: User ID to embed in the token
        company_id: Company ID to embed in the token
        secret_key: Secret key to sign the token
        
    Returns:
        The signed JWT token
    """
    payload = {
        "user_id": user_id,
        "company_id": company_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    
    # For PyJWT >=2.0, jwt.encode returns a string; if bytes, decode it.
    if isinstance(token, bytes):
        token = token.decode("utf-8")
        
    return token

def verify_token(token, secret_key="default_secret"):
    """
    Verify a JWT token
    
    Args:
        token: The token to verify
        secret_key: Secret key for verification
        
    Returns:
        The decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        print("ERROR: Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"ERROR: Invalid token - {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error - {e}")
        return None

def print_token_debug_instructions(token):
    """
    Print instructions for debugging with the token
    
    Args:
        token: The JWT token
    """
    print("\n=== TOKEN DEBUGGING INSTRUCTIONS ===")
    print("1. Use this token for debugging:")
    print(f"   {token}")
    print("\n2. To set this token in browser console:")
    print(f"   document.cookie = 'access_token={token}; path=/; max-age=2592000;'")
    print("\n3. To verify this token in Python:")
    print("   import jwt")
    print(f"   jwt.decode('{token}', 'default_secret', algorithms=['HS256'])")
    print("\n4. To fix the moving parameters page:")
    print("   a. Open your browser to the moving parameters page")
    print("   b. Open the browser console (F12)")
    print("   c. Paste and run the document.cookie command from step 2")
    print("   d. Reload the page")
    print("\n5. Test in curl:")
    print(f"   curl -v -H 'Cookie: access_token={token}' http://localhost:5006/api/companies/moving_parameters")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Generate and verify JWT tokens for testing")
    parser.add_argument("--user-id", type=int, default=23, help="User ID to embed in token")
    parser.add_argument("--company-id", type=int, default=23, help="Company ID to embed in token")
    parser.add_argument("--verify", type=str, help="Verify the given token instead of generating one")
    
    args = parser.parse_args()
    
    if args.verify:
        print(f"Verifying token: {args.verify[:20]}...")
        payload = verify_token(args.verify)
        if payload:
            print(f"Token is valid! Payload: {payload}")
        else:
            print("Token verification failed")
    else:
        token = generate_token(args.user_id, args.company_id)
        print(f"Generated token for user_id={args.user_id}, company_id={args.company_id}:")
        print(token)
        print("\nVerifying the generated token...")
        payload = verify_token(token)
        if payload:
            print(f"Token verification successful! Payload: {payload}")
            print_token_debug_instructions(token)
        else:
            print("Token verification failed")

if __name__ == "__main__":
    main() 