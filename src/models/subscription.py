from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from src.database import Base
from src.subscriptions.features import SubscriptionPlan, Feature

class Subscription(Base):
    """Model for company subscriptions."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    plan = Column(Enum(SubscriptionPlan), nullable=False)
    status = Column(String, nullable=False, default="active")
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    billing_cycle = Column(String, nullable=False, default="monthly")
    payment_method_id = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True, default={})

    # Relationships
    company = relationship("Company", back_populates="subscription")
    features = relationship("SubscriptionFeature", back_populates="subscription")
    history = relationship("SubscriptionHistory", back_populates="subscription")

class SubscriptionFeature(Base):
    """Model for tracking feature usage within subscriptions."""
    __tablename__ = "subscription_features"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    feature = Column(Enum(Feature), nullable=False)
    usage_limit = Column(Integer, nullable=True)
    current_usage = Column(Integer, nullable=False, default=0)
    last_reset = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    subscription = relationship("Subscription", back_populates="features")

class SubscriptionHistory(Base):
    """Model for tracking subscription changes."""
    __tablename__ = "subscription_history"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    event_type = Column(String, nullable=False)
    event_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    subscription = relationship("Subscription", back_populates="history")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)
    payment_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    transaction_id = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True, default={})

    # Relationships
    subscription = relationship("Subscription", backref="payments")

    def __repr__(self):
        return f'<Payment {self.id} - Subscription {self.subscription_id} - Amount {self.amount} {self.currency}>' 