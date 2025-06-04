import os
import jwt
from datetime import datetime, timedelta

def generate_jwt(payload):
    """
    Generates a JWT token with an expiration time.
    
    :param payload: Dictionary of data to encode into the token.
    :return: A JWT token as a string.
    """
    # Set token to expire in 30 days for persistent login.
    expiration = datetime.utcnow() + timedelta(days=30)
    payload.update({"exp": expiration})
    secret_key = os.environ.get("SECRET_KEY", "default_secret")
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    # For PyJWT >=2.0, jwt.encode returns a string; if bytes, decode it.
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def verify_jwt(token):
    """
    Verifies a JWT token and returns its payload if valid.
    
    :param token: The JWT token as a string.
    :return: The decoded payload dictionary if valid; otherwise, None.
    """
    secret_key = os.environ.get("SECRET_KEY", "default_secret")
    
    # Check if token is None or empty
    if not token:
        print("Token is None or empty")
        return None
    
    # Check if this might be a Flask session cookie (most common case)
    if token.startswith('eyJfZnJlc2giOmZhbHNl') or token.startswith('.'):
        print(f"Token appears to be a Flask session cookie, not JWT: {token[:20]}...")
        return None
        
    # Check if it's a valid JWT format (should start with eyJhbGciOiJ)
    if not token.startswith('eyJhbGciOiJ'):
        print(f"Token does not have JWT format: {token[:20]}...")
        return None
    
    try:
        print(f"Attempting to verify JWT: {token[:20]}...")
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        print(f"JWT verification successful. Payload: {payload}")
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired.
        print(f"JWT verification failed: token expired")
        return None
    except jwt.InvalidTokenError as e:
        # Token is invalid.
        print(f"JWT verification failed: invalid token - {str(e)}")
        return None
    except Exception as e:
        # Any other error
        print(f"JWT verification failed with unexpected error: {str(e)}")
        return None
