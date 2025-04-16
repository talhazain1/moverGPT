"""
webhook.py

This module handles incoming Stripe webhook events. It verifies the Stripe signature
and processes events such as checkout session completions, recurring invoice payments,
and subscription deletions.
"""
import logging
import os
import json
import stripe
from flask import request, jsonify
from datetime import datetime
from users.models import User
from users.subscriptions import subscribe_user
from dateutil.relativedelta import relativedelta
from core.database import db

# Load the webhook secret from the environment.
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_default")

# Import our subscription updater (ensure that your PYTHONPATH includes your backend folder)
from users.subscriptions import subscribe_user
from users.models import User

def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", None)
    if not sig_header:
        return jsonify({"error": "Missing Stripe-Signature header"}), 400

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    print('event ' + event_type)

    # Process events
    if event_type == "checkout.session.completed":
        handle_checkout_session_completed(data_object)
    elif event_type == "invoice.payment_succeeded":
        handle_invoice_payment_succeeded(data_object)
    elif event_type == "customer.subscription.deleted":
        handle_subscription_deleted(data_object)
    # Additional events can be handled as needed.

    return jsonify({"status": "success"}), 200

def handle_checkout_session_completed(session: dict):
    import json
    print("DEBUG: Checkout session completed:", json.dumps(session, indent=2))
    
    customer_email = session.get("customer_email")
    if not customer_email:
        print("DEBUG: No customer email found in checkout session")
        return

    # Attempt to extract the subscription from the expanded session
    subscription = session.get("subscription")
    if subscription:
        metadata = subscription.get("metadata", {})
        plan = metadata.get("subscription_plan") or "basic"
        
        # Use trial_end if available; else use current_period_end; else calculate manually
        expires_at = None
        if subscription.get("trial_end"):
            expires_at = datetime.fromtimestamp(subscription["trial_end"])
        elif subscription.get("current_period_end"):
            expires_at = datetime.fromtimestamp(subscription["current_period_end"])
        else:
            # If neither is available, compute: expiry is subscription date plus one month minus one day.
            # Here we assume the subscription date to be now.
            expires_at = datetime.utcnow() + relativedelta(months=1, days=-1)
    else:
        metadata = session.get("metadata", {})
        plan = metadata.get("subscription_plan") or "basic"
        # Fallback: if no subscription object, compute expiry as one month from now minus one day.
        expires_at = datetime.utcnow() + relativedelta(months=1, days=-1)
    
    try:
        user = User.query.filter_by(user_email=customer_email).first()
        if user:
            # Update the user's subscription plan via our subscribe_user helper
            subscribe_user(user.id, plan)
            # Update the expiry date
            user.subscription_expires_at = expires_at
            db.session.commit()
            print(f"DEBUG: Updated user {user.id} with plan '{plan}' expiring on {expires_at}")
        else:
            print(f"DEBUG: No user found with email {customer_email}")
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to update subscription plan and expiry:", e)

def handle_invoice_payment_succeeded(invoice: dict):
    """
    Process a successful recurring invoice payment.
    This event confirms that an auto-renewal charge has been processed.
    
    Args:
        invoice (dict): The invoice object from Stripe.
    """
    subscription_id = invoice.get("subscription")
    amount_paid = invoice.get("amount_paid")
    currency = invoice.get("currency")
    print(f"Auto-renewal payment succeeded for subscription {subscription_id}: {amount_paid} {currency}")
    # TODO: Update your database records for the subscription renewal, log the transaction, etc.

def handle_subscription_deleted(subscription: dict):
    """
    Process a subscription deletion event.
    
    Args:
        subscription (dict): The subscription object from Stripe.
    """
    print("Subscription deleted:", subscription)
    # TODO: Update your database to mark the subscription as canceled.
