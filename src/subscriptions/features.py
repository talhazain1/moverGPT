from enum import Enum
from functools import wraps
from flask import jsonify, current_app
from users.models import User
from typing import List, Dict, Set

class Feature(Enum):
    """Available features in the subscription system."""
    # Basic Features
    CHATBOT = "chatbot"
    KNOWLEDGE_BASE = "knowledge_base"
    SUPPORT_TICKETS = "support_tickets"
    API_ACCESS = "api_access"
    CUSTOM_BRANDING = "custom_branding"
    ANALYTICS = "analytics"
    MULTI_LANGUAGE = "multi_language"
    ADVANCED_AI = "advanced_ai"
    PRIORITY_SUPPORT = "priority_support"
    CUSTOM_INTEGRATIONS = "custom_integrations"
    
    # Chatbot-specific Features
    BASIC_CHATBOT = "basic_chatbot"
    ADVANCED_CHATBOT = "advanced_chatbot"
    ADVANCED_ANALYTICS = "advanced_analytics"
    WHITE_LABEL = "white_label"
    CUSTOM_MODELS = "custom_models"

class SubscriptionPlan(Enum):
    """Available subscription plans."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

# Feature sets for each plan
PLAN_FEATURES = {
    SubscriptionPlan.FREE: {
        Feature.CHATBOT,
        Feature.KNOWLEDGE_BASE,
        Feature.SUPPORT_TICKETS
    },
    SubscriptionPlan.BASIC: {
        Feature.CHATBOT,
        Feature.KNOWLEDGE_BASE,
        Feature.SUPPORT_TICKETS,
        Feature.API_ACCESS,
        Feature.CUSTOM_BRANDING,
        Feature.ANALYTICS
    },
    SubscriptionPlan.PRO: {
        Feature.CHATBOT,
        Feature.KNOWLEDGE_BASE,
        Feature.SUPPORT_TICKETS,
        Feature.API_ACCESS,
        Feature.CUSTOM_BRANDING,
        Feature.ANALYTICS,
        Feature.MULTI_LANGUAGE,
        Feature.ADVANCED_AI,
        Feature.PRIORITY_SUPPORT
    },
    SubscriptionPlan.ENTERPRISE: {
        Feature.CHATBOT,
        Feature.KNOWLEDGE_BASE,
        Feature.SUPPORT_TICKETS,
        Feature.API_ACCESS,
        Feature.CUSTOM_BRANDING,
        Feature.ANALYTICS,
        Feature.MULTI_LANGUAGE,
        Feature.ADVANCED_AI,
        Feature.PRIORITY_SUPPORT,
        Feature.CUSTOM_INTEGRATIONS
    }
}

def has_feature(feature: Feature):
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

def get_available_features(plan: SubscriptionPlan) -> List[Feature]:
    """Get available features for a subscription plan."""
    return list(PLAN_FEATURES.get(plan, []))

def get_plan_features_description(plan: SubscriptionPlan) -> List[str]:
    """Get a human-readable description of features for a plan."""
    features = get_available_features(plan)
    descriptions = {
        Feature.CHATBOT: "Chatbot features",
        Feature.KNOWLEDGE_BASE: "Knowledge base features",
        Feature.SUPPORT_TICKETS: "Support tickets features",
        Feature.API_ACCESS: "API access features",
        Feature.CUSTOM_BRANDING: "Custom branding features",
        Feature.ANALYTICS: "Analytics features",
        Feature.MULTI_LANGUAGE: "Multi-language support",
        Feature.ADVANCED_AI: "Advanced AI features",
        Feature.PRIORITY_SUPPORT: "Priority support features",
        Feature.CUSTOM_INTEGRATIONS: "Custom integrations features"
    }
    return [descriptions[feature] for feature in features]

def get_plan_pricing(plan: SubscriptionPlan) -> Dict:
    """Get pricing information for a subscription plan."""
    pricing = {
        SubscriptionPlan.FREE: {
            "monthly": 0,
            "yearly": 0,
            "limits": {
                "chatbot": 1,
                "knowledge_base": 10,  # documents
                "support_tickets": 10  # per month
            }
        },
        SubscriptionPlan.BASIC: {
            "monthly": 29,
            "yearly": 299,
            "limits": {
                "chatbot": 1,
                "knowledge_base": 50,
                "support_tickets": 50,
                "api_access": 1000,  # API calls per month
                "analytics": "basic"
            }
        },
        SubscriptionPlan.PRO: {
            "monthly": 99,
            "yearly": 999,
            "limits": {
                "chatbot": 1,
                "knowledge_base": 200,
                "support_tickets": 200,
                "api_access": 10000,
                "analytics": "advanced",
                "multi_language": 5,  # languages
                "advanced_ai": True
            }
        },
        SubscriptionPlan.ENTERPRISE: {
            "monthly": "custom",
            "yearly": "custom",
            "limits": {
                "chatbot": 1,
                "knowledge_base": "unlimited",
                "support_tickets": "unlimited",
                "api_access": "unlimited",
                "analytics": "enterprise",
                "multi_language": "unlimited",
                "advanced_ai": True,
                "custom_integrations": True
            }
        }
    }
    return pricing.get(plan, {})

def get_feature_description(feature: Feature) -> str:
    """Returns a human-readable description of the feature."""
    descriptions = {
        Feature.CHATBOT: "Chatbot features",
        Feature.KNOWLEDGE_BASE: "Knowledge base features",
        Feature.SUPPORT_TICKETS: "Support tickets features",
        Feature.API_ACCESS: "API access features",
        Feature.CUSTOM_BRANDING: "Custom branding features",
        Feature.ANALYTICS: "Analytics features",
        Feature.MULTI_LANGUAGE: "Multi-language support",
        Feature.ADVANCED_AI: "Advanced AI features",
        Feature.PRIORITY_SUPPORT: "Priority support features",
        Feature.CUSTOM_INTEGRATIONS: "Custom integrations features"
    }
    return descriptions.get(feature, "No description available") 