from payments import stripe_integration

# Mapping of package names to Stripe Price IDs.
PACKAGE_PRICE_IDS = {
    "basic": "price_1RBGuXDYimJoEAVZCl3cypZl",        # Basic plan: $10/month
    "pro": "price_1RBViSDYimJoEAVZZfsYxw4X",            # Pro plan: $40/month
    "enterprise": "price_1RBVioDYimJoEAVZBcBZPj8C"  # Enterprise plan: $70/month
}

def initiate_payment(customer_email: str, package: str, success_url: str, cancel_url: str) -> str:
    try:
        price_id = PACKAGE_PRICE_IDS.get(package.lower())
        if not price_id:
            raise Exception("Invalid package selected.")
        
        subscription_data = {"metadata": {"subscription_plan": package.lower()}}
        
        session = stripe_integration.create_checkout_session(
            customer_email=customer_email,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data=subscription_data
        )
        return session.url
    except Exception as e:
        raise Exception(f"Failed to initiate payment: {e}")
