import re
import uuid
from flask import Blueprint, request, jsonify, make_response
from users.models import User
from core.database import db
from core.utils import generate_jwt, verify_jwt
from core.email_service import send_verification_email  # If needed
import os

users_bp = Blueprint('users', __name__)

def get_token_from_request():
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and len(auth_header.split(" ")) > 1:
        token = auth_header.split(" ")[-1]
    else:
        token = request.cookies.get("access_token")
    return token

@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    email = data.get("user_email")
    password = data.get("password")
    user_name = data.get("user_name")
    company_name = data.get("company_name")
    if not email or not password or not user_name or not company_name:
        return jsonify({"error": "user_email, user_name, company_name and password are required"}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "Invalid email format"}), 400

    if User.query.filter_by(user_email=email).first():
        return jsonify({"error": "User already exists"}), 400

    try:
        # Create new user
        user = User(
            user_email=email,
            user_name=user_name,
            company_name=company_name,
        )
        user.set_password(password)
        # Bypass email verification for now.
        user.is_verified = True
        db.session.add(user)
        db.session.commit()

        # Ensure company_id is set to the user's id if not provided.
        if not user.company_id:
            user.company_id = user.id
            db.session.commit()

        # Generate JWT token including both user_id and company_id
        token = generate_jwt({"user_id": user.id, "company_id": user.company_id})

        response = make_response(jsonify({
            "message": "User registered successfully",
            "user": {
                "id": user.id,
                "user_name": user.user_name,
                "user_email": user.user_email,
                "user_phone": user.user_phone,
                "company_id": user.company_id,
                "company_name": user.company_name,
                "company_phone": user.company_phone,
                "business_address": user.business_address,
                "company_website": user.company_website,
                "company_logo": user.company_logo,
                "niche": user.niche,
                "subscription_plan": user.subscription_plan,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat()
            }
        }), 201)
        response.set_cookie(
            "access_token", token,
            max_age=60 * 60 * 24 * 30,  # 30 days in seconds
            httponly=True,
            secure=True,                # Set True if serving over HTTPS
            samesite="Lax"
        )
        return response
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Registration failed", "details": str(e)}), 500

@users_bp.route('/verify', methods=['GET'])
def verify():
    token = request.args.get("token")
    email = request.args.get("email")
    if not token or not email:
        return jsonify({"error": "Invalid verification link"}), 400

    user = User.query.filter_by(user_email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.is_verified = True
    db.session.commit()
    return jsonify({"message": "Email verified successfully"}), 200

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    email = data.get("user_email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "user_email and password are required"}), 400

    user = User.query.filter_by(user_email=email).first()
    if user and user.check_password(password):
        token = generate_jwt({"user_id": user.id, "company_id": user.company_id})
        response = make_response(jsonify({
            "message": "Login successful",
            "user": {
                "id": user.id,
                "user_name": user.user_name,
                "user_email": user.user_email,
                "is_verified": user.is_verified,
                "subscription_plan": user.subscription_plan
            }
        }), 200)
        response.set_cookie(
            "access_token", token,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            secure=True,
            samesite="Lax"
        )
        return response

    return jsonify({"error": "Invalid email or password"}), 401

@users_bp.route('/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({"message": "Logged out successfully"}), 200)
    response.delete_cookie("access_token")
    return response

@users_bp.route('/profile', methods=['GET'])
def profile():
    token = get_token_from_request()
    if not token:
        return jsonify({"error": "Token missing"}), 401

    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401

    user = User.query.get(payload.get("user_id"))
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "user": {
            "id": user.id,
            "user_name": user.user_name,
            "user_phone": user.user_phone,
            "user_email": user.user_email,
            "company_id": user.company_id,
            "company_name": user.company_name,
            "company_phone": user.company_phone,
            "business_address": user.business_address,
            "company_website": user.company_website,
            "company_logo": user.company_logo,
            "niche": user.niche,
            "subscription_plan": user.subscription_plan,
            "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            "is_verified": user.is_verified,
            "created_at": user.created_at.isoformat()
        }
    }), 200

@users_bp.route('/upload_logo', methods=['POST'])
def upload_logo():
    token = get_token_from_request()
    if not token:
        return jsonify({"error": "Token missing"}), 401

    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401

    user = User.query.get(payload.get("user_id"))
    if not user:
        return jsonify({"error": "User not found"}), 404

    if 'logo' not in request.files:
        return jsonify({"error": "No logo file provided"}), 400

    logo_file = request.files['logo']
    if not logo_file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        return jsonify({"error": "Invalid file type. Only PNG and JPG are allowed."}), 400

    upload_folder = os.path.join("static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    extension = os.path.splitext(logo_file.filename)[1]
    filename = f"user_{user.id}_{uuid.uuid4().hex}{extension}"
    file_path_on_disk = os.path.join(upload_folder, filename)
    logo_file.save(file_path_on_disk)

    db_path = f"/static/uploads/{filename}"
    user.company_logo = db_path

    try:
        db.session.commit()
        return jsonify({"message": "Logo uploaded successfully", "company_logo": db_path}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update logo", "details": str(e)}), 500

@users_bp.route('/update_profile', methods=['PUT'])
def update_profile():
    token = get_token_from_request()
    if not token:
        return jsonify({"error": "Token missing"}), 401

    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401

    user = User.query.get(payload.get("user_id"))
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}

    if "user_name" in data and data["user_name"].strip() != "":
        user.user_name = data["user_name"]
    if "user_phone" in data and data["user_phone"].strip() != "":
        user.user_phone = data["user_phone"]
    if "company_name" in data and data["company_name"].strip() != "":
        user.company_name = data["company_name"]
    if "company_phone" in data and data["company_phone"].strip() != "":
        user.company_phone = data["company_phone"]
    if "business_address" in data and data["business_address"].strip() != "":
        user.business_address = data["business_address"]
    if "company_website" in data and data["company_website"].strip() != "":
        user.company_website = data["company_website"]
    if "company_logo" in data and data["company_logo"].strip() != "":
        user.company_logo = data["company_logo"]
    if "niche" in data and data["niche"].strip() != "":
        user.niche = data["niche"]

    try:
        db.session.commit()
        return jsonify({
            "message": "Profile updated successfully",
            "user": {
                "id": user.id,
                "user_name": user.user_name,
                "user_phone": user.user_phone,
                "user_email": user.user_email,
                "company_id": user.company_id,
                "company_name": user.company_name,
                "company_phone": user.company_phone,
                "business_address": user.business_address,
                "company_website": user.company_website,
                "company_logo": user.company_logo,
                "niche": user.niche,
                "subscription_plan": user.subscription_plan,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat()
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update profile", "details": str(e)}), 500
