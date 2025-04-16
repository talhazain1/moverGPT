"""
Decorators for checking feature access in routes.
"""

from functools import wraps
from flask import jsonify, request
from core.utils import verify_jwt
from users.models import User
from .features import has_feature

def require_feature(feature: str):
    """
    Decorator to check if the user's subscription plan has access to a specific feature.
    
    Args:
        feature (str): The feature to check access for
        
    Returns:
        function: Decorated route function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get the JWT token from the request
            token = None
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            else:
                token = request.cookies.get("access_token")
            
            if not token:
                return jsonify({"error": "Authorization token missing"}), 401
            
            # Verify the token and get the user
            payload = verify_jwt(token)
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401
            
            user_id = payload.get("user_id")
            user = User.query.get(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            # Check if the user's plan has access to the feature
            if not has_feature(user.subscription_plan or "basic", feature):
                return jsonify({
                    "error": f"Feature '{feature}' not available in your current plan",
                    "required_plan": "pro" if feature.startswith("pro_") else "enterprise"
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator 