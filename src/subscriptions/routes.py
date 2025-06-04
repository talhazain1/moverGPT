from flask import Blueprint, jsonify, request
from .features import SubscriptionPlan, Feature, get_available_features, get_feature_description, get_plan_pricing
from users.models import User
from chatbot.models import ChatbotConfig, ChatSession, ChatMessage
from core.database import db
from .decorators import require_subscription
from functools import wraps
from datetime import datetime
import os
import stripe

# Initialize Stripe with your secret key
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", 
    "sk_test_51R4cQDDYimJoEAVZ1T2pCnOcBACNcSoACRB0FkpfKjM6oqlQpzvVXPvcmcN0uYd0cSbcCQGRV8ypVeuhYlMNG1iz004wW4kNDP")

subscription_bp = Blueprint('subscription', __name__)

@subscription_bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create a Stripe checkout session for subscription purchase."""
    print("DEBUG: create-checkout-session endpoint called")
    try:
        # Get user from cookies
        token = request.cookies.get('access_token')
        print(f"DEBUG: Token in cookie: {token[:10] + '...' if token else 'None'}")
        
        # Print request data for debugging
        print(f"DEBUG: Request method: {request.method}")
        print(f"DEBUG: Request headers: {dict(request.headers)}")
        print(f"DEBUG: Request data: {request.get_data(as_text=True)}")
        
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            error_response = jsonify({"error": "Authentication required"})
            print(f"DEBUG: Returning error: {error_response.get_data(as_text=True)}")
            return error_response, 401
        
        user_id = payload.get("user_id")
        print(f"DEBUG: User ID: {user_id}")
        
        user = User.query.get(user_id)
        
        if not user:
            error_response = jsonify({"error": "User not found"})
            print(f"DEBUG: Returning error: {error_response.get_data(as_text=True)}")
            return error_response, 404
        
        # Get the price ID and plan name from the request
        data = request.get_json()
        print(f"DEBUG: Got request data: {data}")
        price_id = data.get('price_id')
        plan_name = data.get('plan_name')
        
        if not price_id or not plan_name:
            error_response = jsonify({"error": "Price ID and plan name are required"})
            print(f"DEBUG: Returning error: {error_response.get_data(as_text=True)}")
            return error_response, 400
        
        # Create a checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            customer_email=user.user_email,
            success_url=request.host_url + 'static/success.html?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'static/pricing.html',
            subscription_data={
                'trial_period_days': 7,
                'metadata': {
                    'user_id': user_id,
                    'subscription_plan': plan_name,
                    'company_id': user.company_id or user_id
                }
            }
        )
        
        response_data = {
            'id': session.id,
            'url': session.url
        }
        print(f"DEBUG: Created checkout session: {response_data}")
        success_response = jsonify(response_data)
        print(f"DEBUG: Returning success: {success_response.get_data(as_text=True)}")
        return success_response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DEBUG: Error creating checkout session: {str(e)}")
        error_response = jsonify({"error": str(e)})
        print(f"DEBUG: Returning exception: {error_response.get_data(as_text=True)}")
        return error_response, 500

@subscription_bp.route('/details', methods=['GET'])
def get_subscription_details():
    """Get detailed subscription information for a user, including limits and usage."""
    try:
        # Get user from token or session
        token = None
        
        # Try to get token from cookies - use access_token cookie name
        token = request.cookies.get('access_token')
        print(f"DEBUG: Token from cookie: {token[:10] + '...' if token else None}")
        
        # If not in cookies, try from Authorization header
        if not token:
            auth_header = request.headers.get('Authorization')
            print(f"DEBUG: Auth header: {auth_header[:20] + '...' if auth_header else None}")
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print(f"DEBUG: Token from Authorization header: {token[:10] + '...' if token else None}")
        
        # If still no token, try to get from query parameters
        if not token:
            token = request.args.get('token')
            print(f"DEBUG: Token from query param: {token[:10] + '...' if token else None}")
            
        # If we still don't have a token, check session
        if not token and hasattr(request, 'session') and 'user_id' in request.session:
            user_id = request.session['user_id']
            print(f"DEBUG: User ID from session: {user_id}")
            user = User.query.get(user_id)
            if user:
                return build_subscription_response(user)
        
        # If we still don't have a token, return error with status 200
        if not token:
            print("DEBUG: No token found in cookies, headers, query parameters, or session")
            return jsonify({
                "error": "Authentication required", 
                "success": False,
                "subscription": {"plan": "free", "plan_display_name": "Free"}
            }), 200  # Return 200 instead of 401 to prevent redirect
        
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            print(f"DEBUG: Invalid token: {token[:10] + '...' if token else None}")
            return jsonify({
                "error": "Invalid or expired token", 
                "success": False,
                "subscription": {"plan": "free", "plan_display_name": "Free"}
            }), 200  # Return 200 instead of 401 to prevent redirect
        
        user_id = payload.get("user_id")
        print(f"DEBUG: User ID from token: {user_id}")
        
        user = User.query.get(user_id)
        
        if not user:
            print(f"DEBUG: User not found with ID {user_id}")
            return jsonify({
                "error": "User not found", 
                "success": False,
                "subscription": {"plan": "free", "plan_display_name": "Free"}
            }), 200  # Return 200 instead of 404 to prevent redirect
        
        return build_subscription_response(user)
    except Exception as e:
        print(f"DEBUG: Error in subscription details endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return a default "free" plan response in case of any error
        return jsonify({
            "success": False,
            "error": str(e),
            "subscription": {
                "plan": "free",
                "plan_display_name": "Free",
                "status": "active",
                "expires_at": None,
                "days_remaining": 0
            },
            "limits": {
                "chatbot": 1,
                "knowledge_base": 10,
                "support_tickets": 10
            },
            "usage": {
                "chatbots": 0,
                "messages": 0
            },
            "features": []
        }), 200  # Still return 200 to prevent frontend errors

def build_subscription_response(user):
    """Build the subscription response for a user"""
    print(f"DEBUG: Building subscription for user {user.user_name}, subscription plan: {user.subscription_plan}")
    
    # Default to free if no plan is set
    plan_name = user.subscription_plan or "free"
    
    try:
        # Convert to enum
        plan = SubscriptionPlan(plan_name)
    except ValueError:
        # If plan doesn't match enum values, default to free
        print(f"DEBUG: Invalid plan '{plan_name}', defaulting to FREE")
        plan = SubscriptionPlan.FREE
        plan_name = "free"
        
    # Get pricing and limits for the plan
    plan_pricing = get_plan_pricing(plan)
    
    # Calculate usage
    company_id = user.company_id or user.id
    print(f"DEBUG: Using company ID: {company_id}")
    
    chatbots_count = ChatbotConfig.query.filter_by(company_id=company_id).count()
    print(f"DEBUG: Found {chatbots_count} chatbots")
    
    # Get all sessions for user's chatbots
    chatbot_ids = db.session.query(ChatbotConfig.id).filter_by(company_id=company_id).all()
    chatbot_ids = [c[0] for c in chatbot_ids]
    
    total_messages = 0
    if chatbot_ids:
        # Count all messages for this user's chatbots
        total_messages = db.session.query(db.func.count(ChatMessage.id)).join(
            ChatSession, ChatMessage.session_id == ChatSession.id
        ).filter(
            ChatSession.chatbot_id.in_(chatbot_ids)
        ).scalar() or 0
    
    print(f"DEBUG: Found {total_messages} messages")
    
    # Format expiry date
    expiry_date = None
    days_remaining = 0
    
    if user.subscription_expires_at:
        expiry_date = user.subscription_expires_at.isoformat()
        today = datetime.utcnow().date()
        days_remaining = (user.subscription_expires_at.date() - today).days
    
    # Build the response
    response = {
        "success": True,
        "subscription": {
            "plan": plan_name,
            "plan_display_name": plan_name.capitalize(),
            "status": user.subscription_status or "active",
            "expires_at": expiry_date,
            "days_remaining": days_remaining,
            "monthly_price": plan_pricing.get("monthly", 0),
            "yearly_price": plan_pricing.get("yearly", 0)
        },
        "limits": plan_pricing.get("limits", {}),
        "usage": {
            "chatbots": chatbots_count,
            "messages": total_messages
        },
        "features": [
            {"name": feature.name, "available": True, "description": get_feature_description(feature)}
            for feature in get_available_features(plan)
        ]
    }
    
    return jsonify(response), 200

@subscription_bp.route('/api/subscription/features', methods=['GET'])
@require_subscription
def get_features():
    """Get available features for the current subscription plan."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID not provided"}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    current_plan = SubscriptionPlan(user.subscription_plan)
    available_features = get_available_features(current_plan)
    
    # Get all features with their descriptions and availability
    all_features = []
    for feature in Feature:
        feature_info = {
            "name": feature.value,
            "description": get_feature_description(feature),
            "available": feature in available_features,
            "required_plan": None
        }
        
        # Determine which plan is required for this feature
        for plan in SubscriptionPlan:
            if feature in get_available_features(plan):
                feature_info["required_plan"] = plan.value
                break
        
        all_features.append(feature_info)
    
    return jsonify({
        "current_plan": current_plan.value,
        "features": all_features
    })

@subscription_bp.route('/api/subscription/upgrade', methods=['POST'])
@require_subscription
def upgrade_subscription():
    """Handle subscription upgrade requests."""
    data = request.get_json()
    user_id = data.get('user_id')
    new_plan = data.get('plan')
    
    if not user_id or not new_plan:
        return jsonify({"error": "User ID and plan are required"}), 400
    
    try:
        new_plan = SubscriptionPlan(new_plan)
    except ValueError:
        return jsonify({"error": "Invalid plan"}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    current_plan = SubscriptionPlan(user.subscription_plan)
    
    # Check if the upgrade is valid
    if new_plan.value == current_plan.value:
        return jsonify({"error": "Already on this plan"}), 400
    
    # Update the subscription plan
    user.subscription_plan = new_plan.value
    db.session.commit()
    
    return jsonify({
        "message": f"Successfully upgraded to {new_plan.value} plan",
        "new_plan": new_plan.value,
        "features": get_available_features(new_plan)
    })

@subscription_bp.route('/api/subscription/check-feature', methods=['GET'])
@require_subscription
def check_feature():
    """Check if a specific feature is available for the current subscription."""
    user_id = request.args.get('user_id')
    feature_name = request.args.get('feature')
    
    if not user_id or not feature_name:
        return jsonify({"error": "User ID and feature name are required"}), 400
    
    try:
        feature = Feature(feature_name)
    except ValueError:
        return jsonify({"error": "Invalid feature"}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    current_plan = SubscriptionPlan(user.subscription_plan)
    available_features = get_available_features(current_plan)
    
    # Find the minimum plan that includes this feature
    required_plan = None
    for plan in SubscriptionPlan:
        if feature in get_available_features(plan):
            required_plan = plan
            break
    
    return jsonify({
        "feature": feature.value,
        "available": feature in available_features,
        "current_plan": current_plan.value,
        "required_plan": required_plan.value if required_plan else None,
        "description": get_feature_description(feature)
    }) 