"""
Feature definitions for different subscription plans.
"""

from typing import Dict, List, Set

# Define available features
class Features:
    # Basic features
    BASIC_CHATBOT = "basic_chatbot"
    CUSTOM_BOT_NAME = "custom_bot_name"
    BASIC_ANALYTICS = "basic_analytics"
    EMAIL_SUPPORT = "email_support"
    
    # Pro features (includes all basic features)
    ADVANCED_CHATBOT = "advanced_chatbot"
    CUSTOM_BRANDING = "custom_branding"
    ADVANCED_ANALYTICS = "advanced_analytics"
    API_ACCESS = "api_access"
    PRIORITY_SUPPORT = "priority_support"
    
    # Enterprise features (includes all pro features)
    WHITE_LABEL = "white_label"
    CUSTOM_INTEGRATIONS = "custom_integrations"
    DEDICATED_SUPPORT = "dedicated_support"
    MULTIPLE_CHATBOTS = "multiple_chatbots"
    CUSTOM_MODELS = "custom_models"

# Define features available for each plan
PLAN_FEATURES: Dict[str, Set[str]] = {
    "basic": {
        Features.BASIC_CHATBOT,
        Features.CUSTOM_BOT_NAME,
        Features.BASIC_ANALYTICS,
        Features.EMAIL_SUPPORT
    },
    "pro": {
        Features.BASIC_CHATBOT,
        Features.CUSTOM_BOT_NAME,
        Features.BASIC_ANALYTICS,
        Features.EMAIL_SUPPORT,
        Features.ADVANCED_CHATBOT,
        Features.CUSTOM_BRANDING,
        Features.ADVANCED_ANALYTICS,
        Features.API_ACCESS,
        Features.PRIORITY_SUPPORT
    },
    "enterprise": {
        Features.BASIC_CHATBOT,
        Features.CUSTOM_BOT_NAME,
        Features.BASIC_ANALYTICS,
        Features.EMAIL_SUPPORT,
        Features.ADVANCED_CHATBOT,
        Features.CUSTOM_BRANDING,
        Features.ADVANCED_ANALYTICS,
        Features.API_ACCESS,
        Features.PRIORITY_SUPPORT,
        Features.WHITE_LABEL,
        Features.CUSTOM_INTEGRATIONS,
        Features.DEDICATED_SUPPORT,
        Features.MULTIPLE_CHATBOTS,
        Features.CUSTOM_MODELS
    }
}

def has_feature(plan: str, feature: str) -> bool:
    """
    Check if a given plan has access to a specific feature.
    
    Args:
        plan (str): The subscription plan (basic, pro, or enterprise)
        feature (str): The feature to check access for
        
    Returns:
        bool: True if the plan has access to the feature, False otherwise
    """
    plan = plan.lower()
    if plan not in PLAN_FEATURES:
        return False
    return feature in PLAN_FEATURES[plan]

def get_available_features(plan: str) -> List[str]:
    """
    Get all features available for a given plan.
    
    Args:
        plan (str): The subscription plan (basic, pro, or enterprise)
        
    Returns:
        List[str]: List of available features for the plan
    """
    plan = plan.lower()
    if plan not in PLAN_FEATURES:
        return []
    return sorted(list(PLAN_FEATURES[plan])) 