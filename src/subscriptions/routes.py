"""
Routes for subscription-related functionality.
"""

from flask import Blueprint, jsonify, request
from core.utils import verify_jwt
from users.models import User
from .features import get_available_features

subscriptions_bp = Blueprint('subscriptions', __name__)

@subscriptions_bp.route('/features', methods=['GET'])
def get_features():
    """
    Get all features available for the user's current subscription plan.
    """
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
    
    # Get available features for the user's plan
    features = get_available_features(user.subscription_plan or "basic")
    
    return jsonify({
        "subscription_plan": user.subscription_plan or "basic",
        "available_features": features
    }), 200 