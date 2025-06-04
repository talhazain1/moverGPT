from functools import wraps
from flask import jsonify, request
from users.models import User
from .features import Feature, SubscriptionPlan, PLAN_FEATURES

def require_subscription(f):
    """Decorator to ensure user has an active subscription."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.args.get('user_id') or request.json.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID not provided"}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        if not user.subscription_plan:
            return jsonify({"error": "No active subscription"}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_feature(feature: Feature):
    """Decorator to check if user has access to a specific feature."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = kwargs.get('user_id')
            if not user_id:
                return jsonify({"error": "User ID not provided"}), 400
            
            user = User.query.get(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            current_plan = SubscriptionPlan(user.subscription_plan)
            if feature in PLAN_FEATURES[current_plan]:
                return f(*args, **kwargs)
            else:
                return jsonify({
                    "error": "Feature not available",
                    "message": f"Upgrade to {SubscriptionPlan.ENTERPRISE.value} plan to use this feature",
                    "required_plan": SubscriptionPlan.ENTERPRISE.value
                }), 403
        
        return decorated_function
    return decorator 