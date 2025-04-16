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
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired.
        return None
    except jwt.InvalidTokenError:
        # Token is invalid.
        return None
