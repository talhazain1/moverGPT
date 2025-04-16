from flask import Blueprint, request, jsonify
from payments.services import initiate_payment
import os
import stripe
from users.models import User
from users.subscriptions import subscribe_user

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/initiate_payment', methods=['POST'])
def initiate_payment_route():
    try:
        data = request.get_json()
        customer_email = data.get("customer_email")
        package = data.get("package")
        success_url = data.get("success_url")
        cancel_url = data.get("cancel_url")
        
        if not customer_email or not package or not success_url or not cancel_url:
            return jsonify({"error": "Missing required parameters"}), 400
        
        checkout_url = initiate_payment(customer_email, package, success_url, cancel_url)
        return jsonify({"checkout_url": checkout_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@payments_bp.route('/update_subscription', methods=['POST'])
def update_subscription():
    data = request.get_json()
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400
    try:
        # Retrieve the checkout session from Stripe and expand subscription
        session = stripe.checkout.Session.retrieve(
            session_id, expand=["subscription"]
        )
        customer_email = session.get("customer_email")
        if not customer_email:
            return jsonify({"error": "Customer email not found in session"}), 400

        # Retrieve the subscription and get its metadata
        subscription = session.get("subscription")
        if subscription:
            metadata = subscription.get("metadata", {})
            plan = metadata.get("subscription_plan")
        else:
            plan = "basic"

        # Update the user record based on customer_email
        user = User.query.filter_by(user_email=customer_email).first()
        if user:
            subscribe_user(user.id, plan)
            return jsonify({"message": "Subscription updated", "subscription_plan": plan}), 200
        else:
            return jsonify({"error": f"No user found with email {customer_email}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500