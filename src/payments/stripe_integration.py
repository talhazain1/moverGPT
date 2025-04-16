import os
import stripe

# Using the provided test API key.
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", 
    "sk_test_51R4cQDDYimJoEAVZ1T2pCnOcBACNcSoACRB0FkpfKjM6oqlQpzvVXPvcmcN0uYd0cSbcCQGRV8ypVeuhYlMNG1iz004wW4kNDP")

def create_checkout_session(customer_email: str, price_id: str, success_url: str, cancel_url: str, subscription_data: dict = None):
    if subscription_data is None:
        subscription_data = {}
    subscription_data.setdefault("trial_period_days", 7)
    if "metadata" not in subscription_data:
        subscription_data["metadata"] = {}
    # subscription_data should already include the chosen plan via metadata.
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{"price": price_id, "quantity": 1}],
            subscription_data=subscription_data,
            customer_email=customer_email,
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            expand=["subscription"]  # Expand subscription to get metadata
        )
        return session
    except Exception as e:
        raise Exception(f"Stripe checkout session creation failed: {e}")
