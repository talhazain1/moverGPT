# users/models.py

from core.database import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_name = db.Column(db.String(100), nullable=False)
    user_phone = db.Column(db.String(50), nullable=True)
    user_email = db.Column(db.String(120), unique=True, nullable=False)
    company_id = db.Column(db.Integer, nullable=True)  # or whatever
    company_name = db.Column(db.String(255), nullable=True)
    company_phone = db.Column(db.String(50), nullable=True)
    business_address = db.Column(db.String(255), nullable=True)
    company_website = db.Column(db.String(255), nullable=True)
    company_logo = db.Column(db.String(255), nullable=True)
    niche = db.Column(db.String(50), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    subscription_plan = db.Column(db.String(50), nullable=True)
    subscription_expires_at = db.Column(db.DateTime, nullable=True)
    subscription_status = db.Column(db.String(50), default='active')
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    def subscribe_user(user_id: int, subscription_plan: str) -> bool:
        try:
            user = User.query.get(user_id)
            if not user:
                raise Exception("User not found")
            user.subscription_plan = subscription_plan
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Subscription update failed: {e}")
        

    def __init__(self, user_email, user_name=None, company_name=None, password_hash=None, is_verified=False):
        self.user_email = user_email
        self.user_name = user_name
        self.company_name = company_name
        self.password_hash = password_hash
        self.subscription_plan = 'basic'  # Default to basic plan
        self.subscription_status = 'active'
        self.is_verified = is_verified
    
    def has_feature(self, feature):
        """Check if user has access to a specific feature based on their subscription plan."""
        from subscriptions.features import Features, get_available_features
        available_features = get_available_features(self.subscription_plan)
        return feature in available_features
    
    def upgrade_plan(self, new_plan):
        """Upgrade user's subscription plan."""
        if new_plan not in ['basic', 'pro', 'enterprise']:
            raise ValueError("Invalid subscription plan")
        self.subscription_plan = new_plan
        self.subscription_status = 'active'
        # You might want to update subscription_end_date here based on your billing logic
    
    def cancel_subscription(self):
        """Cancel user's subscription."""
        self.subscription_status = 'canceled'
