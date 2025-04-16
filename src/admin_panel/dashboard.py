"""
Dashboard Module

Generates a dashboard report for a company.
Includes company logo, company name, business email, contact details,
subscription plan, and payment expiry date.
Assumes that the User model holds company details.
"""

from users.models import User
from chatbot.models import ChatbotConfig

def generate_dashboard(company_id: int) -> dict:
    try:
        from users.models import User
        # Query using company_id or fallback to user id.
        user = User.query.filter((User.company_id == company_id) | (User.id == company_id)).first()
        if not user:
            raise Exception("Company/user not found")
        
        payment_expiry = "2025-12-31" if user.subscription_plan != "free_trial" else None

        dashboard_data = {
            "user_name": user.user_name or "",
            "company_logo": user.company_logo or "",
            "company_name": user.company_name or "",
            "business_email": user.user_email or "",
            "contact_details": {
                "phone": user.user_phone or "",
                "company_phone": user.company_phone or "",
                "business_address": user.business_address or ""
            },
            "subscription_plan": user.subscription_plan or "",
            "payment_expiry_date": payment_expiry or ""
        }
        return dashboard_data
    except Exception as e:
        raise Exception(f"Error generating dashboard: {e}")
