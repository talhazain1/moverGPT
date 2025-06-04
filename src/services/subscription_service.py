from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from src.models.subscription import Subscription, SubscriptionFeature, SubscriptionHistory, Payment
from src.subscriptions.features import SubscriptionPlan, Feature, get_available_features, get_plan_pricing
from src.database import get_db

class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def create_subscription(self, company_id: int, plan: SubscriptionPlan, billing_cycle: str = "monthly") -> Subscription:
        """Create a new subscription for a company."""
        subscription = Subscription(
            company_id=company_id,
            plan=plan,
            billing_cycle=billing_cycle,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30 if billing_cycle == "monthly" else 365)
        )
        
        # Add subscription features based on plan
        plan_features = get_available_features(plan)
        for feature in plan_features:
            subscription.features.append(
                SubscriptionFeature(
                    feature=feature,
                    usage_limit=get_plan_pricing(plan)["limits"].get(feature.name, None)
                )
            )

        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)

        # Record subscription creation in history
        self._record_history(subscription.id, "subscription_created", {
            "plan": plan.value,
            "billing_cycle": billing_cycle
        })

        return subscription

    def get_subscription(self, company_id: int) -> Optional[Subscription]:
        """Get the active subscription for a company."""
        return self.db.query(Subscription).filter(
            Subscription.company_id == company_id,
            Subscription.status == "active"
        ).first()

    def update_subscription(self, subscription_id: int, plan: Optional[SubscriptionPlan] = None,
                          status: Optional[str] = None) -> Subscription:
        """Update an existing subscription."""
        subscription = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            raise ValueError("Subscription not found")

        if plan and plan != subscription.plan:
            # Record plan change in history
            self._record_history(subscription.id, "plan_changed", {
                "previous_plan": subscription.plan.value,
                "new_plan": plan.value
            })
            subscription.plan = plan

        if status and status != subscription.status:
            self._record_history(subscription.id, "status_changed", {
                "previous_status": subscription.status,
                "new_status": status
            })
            subscription.status = status

        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def cancel_subscription(self, subscription_id: int) -> Subscription:
        """Cancel a subscription."""
        subscription = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            raise ValueError("Subscription not found")

        subscription.status = "cancelled"
        subscription.end_date = datetime.utcnow()

        self._record_history(subscription.id, "subscription_cancelled", {
            "cancelled_at": datetime.utcnow().isoformat()
        })

        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def record_payment(self, subscription_id: int, amount: int, currency: str,
                      payment_method: str, transaction_id: Optional[str] = None) -> Payment:
        """Record a payment for a subscription."""
        payment = Payment(
            subscription_id=subscription_id,
            amount=amount,
            currency=currency,
            status="completed",
            payment_method=payment_method,
            transaction_id=transaction_id
        )

        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        self._record_history(subscription_id, "payment_received", {
            "amount": amount,
            "currency": currency,
            "transaction_id": transaction_id
        })

        return payment

    def check_feature_access(self, subscription_id: int, feature: Feature) -> bool:
        """Check if a subscription has access to a specific feature."""
        subscription = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription or subscription.status != "active":
            return False

        feature_record = self.db.query(SubscriptionFeature).filter(
            SubscriptionFeature.subscription_id == subscription_id,
            SubscriptionFeature.feature == feature
        ).first()

        if not feature_record:
            return False

        if feature_record.usage_limit is not None:
            return feature_record.current_usage < feature_record.usage_limit

        return True

    def increment_feature_usage(self, subscription_id: int, feature: Feature) -> None:
        """Increment the usage count for a feature."""
        feature_record = self.db.query(SubscriptionFeature).filter(
            SubscriptionFeature.subscription_id == subscription_id,
            SubscriptionFeature.feature == feature
        ).first()

        if feature_record:
            feature_record.current_usage += 1
            self.db.commit()

    def _record_history(self, subscription_id: int, event_type: str, event_data: Dict) -> None:
        """Record an event in the subscription history."""
        history = SubscriptionHistory(
            subscription_id=subscription_id,
            event_type=event_type,
            event_data=event_data
        )
        self.db.add(history)
        self.db.commit()

    def get_subscription_history(self, subscription_id: int) -> List[SubscriptionHistory]:
        """Get the history of events for a subscription."""
        return self.db.query(SubscriptionHistory).filter(
            SubscriptionHistory.subscription_id == subscription_id
        ).order_by(SubscriptionHistory.created_at.desc()).all()

    def get_active_subscription(self, company_id: int) -> Optional[Subscription]:
        """Get the active subscription for a company."""
        return self.db.query(Subscription).filter(
            Subscription.company_id == company_id,
            Subscription.status == "active",
            Subscription.end_date > datetime.utcnow()
        ).first()

    def get_subscription_pricing(self, plan: SubscriptionPlan) -> Dict:
        """Get pricing information for a subscription plan."""
        return get_plan_pricing(plan) 