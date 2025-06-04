import re
import uuid
import secrets
from flask import Blueprint, request, jsonify, make_response, current_app
from users.models import User
from core.database import db
from core.utils import generate_jwt, verify_jwt
from core.email_service import send_verification_email, verify_otp, send_password_reset_email
import os
from datetime import datetime, timedelta
from chatbot.models import ChatbotConfig, ChatMessage, ChatSession
from sqlalchemy import func, text, inspect
import time
from werkzeug.security import check_password_hash
import jwt
import logging

users_bp = Blueprint('users', __name__)

# Add these constants at the top of the file
PASSWORD_RESET_SECRET = "your-password-reset-secret"  # In production, use a secure secret
PASSWORD_RESET_EXPIRY = 3600  # 1 hour in seconds

def get_token_from_request():
    # First check for JWT token in cookie
    token = request.cookies.get("access_token")
    if token and token.startswith('eyJhbGciOiJ'):
        print(f"DEBUG: Using JWT token from cookie")
        return token
    
    # If not found or not a JWT, check for session token    
    session_token = request.cookies.get("flask_session")
    if session_token:
        print(f"DEBUG: Found Flask session token")
        # Handle Flask session authentication differently if needed
        # For now, we just log it and continue with other authentication methods
        
    # Then check Authorization header as fallback
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        print(f"DEBUG: Using token from Authorization header")
        return token
        
    return None

def get_logged_in_company_id():
    """
    Extracts the company_id from the JWT (or cookie) from the request.
    Returns a tuple: (company_id, error_response, status_code)
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.cookies.get("access_token")
    
    if not token:
        return None, jsonify({"error": "Authorization token missing"}), 401

    payload = verify_jwt(token)
    if not payload:
        return None, jsonify({"error": "Invalid or expired token"}), 401

    # Get the user ID from the payload
    user_id = payload.get("user_id")
    if not user_id:
        return None, jsonify({"error": "Invalid token format - missing user_id"}), 401

    # Check for company_id in the payload first
    company_id = payload.get("company_id")
    if company_id:
        return company_id, None, None

    # If not in payload, get the user from the database
    user = User.query.get(user_id)
    if not user:
        return None, jsonify({"error": "User not found"}), 404
    
    # Return company_id if available; otherwise fallback to user.id.
    return user.company_id or user.id, None, None

@users_bp.route('/company/api-key', methods=['GET'])
def get_company_api_key():
    """
    Fetch the API key for the current user's company.
    This endpoint is used by the static dashboard to get the API key for script generation.
    """
    logger = logging.getLogger(__name__)
    logger.info("Fetching API key for company")
    
    # Get the company ID from the JWT token or session
    try:
        # Try to get from JWT first
        company_id, error_response, status_code = get_logged_in_company_id()
        if error_response:
            # If JWT fails, try to get from session (for direct route calls)
            if hasattr(current_app, 'login_manager') and hasattr(current_app.login_manager, 'current_user'):
                from flask_login import current_user
                if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                    if hasattr(current_user, 'company_id') and current_user.company_id:
                        company_id = current_user.company_id
                        logger.info(f"Got company ID from session: {company_id}")
                    elif hasattr(current_user, 'id'):
                        company_id = current_user.id
                        logger.info(f"Using user ID as company ID: {company_id}")
                    else:
                        return error_response, status_code
                else:
                    return error_response, status_code
            else:
                return error_response, status_code
    except Exception as auth_err:
        logger.error(f"Authentication error: {str(auth_err)}", exc_info=True)
        return jsonify({"error": "Authentication error", "success": False}), 401
    
    if not company_id:
        logger.error("No company ID found in token or session")
        return jsonify({"error": "No company ID found", "success": False}), 404
    
    logger.info(f"Looking up API key for company ID: {company_id}")
    
    try:
        # Use raw SQL to get the API key for the company
        import traceback
        
        # Try multiple approaches to find the API key
        api_key = None
        error_messages = []
        
        # Approach 1: Try with status column
        try:
            logger.info(f"Attempting to find API key using status column for company ID: {company_id}")
            sql = text("""
                SELECT key FROM api_keys 
                WHERE company_id = :company_id AND (status = 'active' OR status IS NULL)
                ORDER BY created_at DESC LIMIT 1
            """)
            
            result = db.session.execute(sql, {"company_id": company_id})
            api_key_row = result.fetchone()
            
            if api_key_row:
                api_key = api_key_row[0]
                logger.info(f"API key found using status column for company ID: {company_id}")
        except Exception as e1:
            error_message = f"Error finding API key using status column: {str(e1)}"
            logger.warning(error_message)
            error_messages.append(error_message)
            logger.debug(traceback.format_exc())
        
        # Approach 2: Try with active column if first approach failed
        if not api_key:
            try:
                logger.info(f"Attempting to find API key using active column for company ID: {company_id}")
                sql_alt = text("""
                    SELECT key FROM api_keys 
                    WHERE company_id = :company_id AND (active = TRUE OR active IS NULL)
                    ORDER BY created_at DESC LIMIT 1
                """)
                
                result_alt = db.session.execute(sql_alt, {"company_id": company_id})
                api_key_alt_row = result_alt.fetchone()
                
                if api_key_alt_row:
                    api_key = api_key_alt_row[0]
                    logger.info(f"API key found using active column for company ID: {company_id}")
            except Exception as e2:
                error_message = f"Error finding API key using active column: {str(e2)}"
                logger.warning(error_message)
                error_messages.append(error_message)
                logger.debug(traceback.format_exc())
        
        # Approach 3: Try with no conditions if previous approaches failed
        if not api_key:
            try:
                logger.info(f"Attempting to find any API key for company ID: {company_id}")
                sql_any = text("""
                    SELECT key FROM api_keys 
                    WHERE company_id = :company_id
                    ORDER BY created_at DESC LIMIT 1
                """)
                
                result_any = db.session.execute(sql_any, {"company_id": company_id})
                api_key_any_row = result_any.fetchone()
                
                if api_key_any_row:
                    api_key = api_key_any_row[0]
                    logger.info(f"API key found using no conditions for company ID: {company_id}")
            except Exception as e3:
                error_message = f"Error finding API key using no conditions: {str(e3)}"
                logger.warning(error_message)
                error_messages.append(error_message)
                logger.debug(traceback.format_exc())
        
        # Return the API key if found
        if api_key:
            logger.info(f"Successfully found API key for company ID: {company_id}")
            return jsonify({
                "success": True,
                "api_key": api_key,
                "company_id": company_id
            })
        
        # No API key found
        logger.warning(f"No API key found for company ID: {company_id}")
        return jsonify({
            "success": False,
            "error": "No API key found for this company",
            "company_id": company_id,
            "details": error_messages
        }), 404
    except Exception as e:
        logger.error(f"Error fetching API key: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Error fetching API key: {str(e)}",
            "company_id": company_id
        }), 500

@users_bp.route('/get-api-key', methods=['GET'])
def get_api_key():
    """
    Get the API key for the company.
    This endpoint is used by the dashboard to get API keys.
    """
    logger = logging.getLogger(__name__)
    logger.info("Getting API key")
    
    # Get the company ID from the JWT token or session
    try:
        company_id, error_response, status_code = get_logged_in_company_id()
        if error_response:
            return error_response, status_code
    except Exception as auth_err:
        logger.error(f"Authentication error: {str(auth_err)}", exc_info=True)
        return jsonify({"error": "Authentication error", "success": False}), 401
    
    if not company_id:
        logger.error("No company ID found in token or session")
        return jsonify({"error": "No company ID found", "success": False}), 404
    
    # First, check if the api_keys table exists
    try:
        inspector = inspect(db.engine)
        
        # If the table doesn't exist, create a temporary API key
        if 'api_keys' not in inspector.get_table_names():
            logger.warning("api_keys table doesn't exist, returning temporary API key")
            temp_api_key = f"temp_{secrets.token_hex(16)}"
            
            return jsonify({
                "success": True,
                "api_key": temp_api_key,
                "company_id": company_id,
                "temporary": True,
                "message": "Temporary API key provided - database setup required"
            })
        
        # Table exists, proceed with normal flow
        try:
            # Query for the API key using the status column
            sql = text("""
                SELECT key FROM api_keys 
                WHERE company_id = :company_id AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """)
            
            result = db.session.execute(sql, {"company_id": company_id})
            api_key_row = result.fetchone()
            
            if api_key_row:
                api_key = api_key_row[0]
                logger.info(f"API key found for company ID: {company_id}")
                
                return jsonify({
                    "success": True,
                    "api_key": api_key,
                    "company_id": company_id
                })
            else:
                # No API key found, create one
                logger.info(f"No API key found for company {company_id}, creating new one")
                
                # Generate a new API key with a secure random string
                api_key = f"sk_{secrets.token_hex(24)}"
                
                # Insert the new API key
                try:
                    # Get the user's subscription plan
                    user = User.query.get(company_id)
                    subscription_plan = user.subscription_plan or 'basic'
                    
                    insert_sql = text("""
                        INSERT INTO api_keys (company_id, key, status, created_at, subscription_plan)
                        VALUES (:company_id, :key, 'active', NOW(), :subscription_plan)
                        RETURNING id
                    """)
                    
                    insert_result = db.session.execute(insert_sql, {
                        "company_id": company_id,
                        "key": api_key,
                        "subscription_plan": subscription_plan
                    })
                    
                    # Get the ID of the new API key
                    api_key_id = insert_result.scalar()
                    
                    # Commit the transaction
                    db.session.commit()
                    
                    logger.info(f"New API key created for company ID: {company_id}")
                    
                    return jsonify({
                        "success": True,
                        "api_key": api_key,
                        "company_id": company_id,
                        "api_key_id": api_key_id,
                        "message": "New API key created"
                    })
                except Exception as db_err:
                    db.session.rollback()
                    logger.error(f"Database error creating API key: {str(db_err)}", exc_info=True)
                    
                    # Return a temporary API key as fallback
                    temp_api_key = f"temp_{secrets.token_hex(16)}"
                    logger.info(f"Returning temporary API key for company ID: {company_id}")
                    
                    return jsonify({
                        "success": True,
                        "api_key": temp_api_key,
                        "company_id": company_id,
                        "temporary": True,
                        "message": "Temporary API key provided - database error"
                    })
        except Exception as query_err:
            logger.error(f"Error querying API key: {str(query_err)}", exc_info=True)
            
            # Return a temporary API key as fallback
            temp_api_key = f"temp_{secrets.token_hex(16)}"
            logger.info(f"Returning temporary API key for company ID: {company_id}")
            
            return jsonify({
                "success": True,
                "api_key": temp_api_key,
                "company_id": company_id,
                "temporary": True,
                "message": "Temporary API key provided - query error"
            })
    except Exception as e:
        logger.error(f"Error getting/creating API key: {str(e)}", exc_info=True)
        
        # Return a temporary API key as last resort
        temp_api_key = f"temp_{secrets.token_hex(16)}"
        logger.info(f"Returning temporary API key for company ID: {company_id}")
        
        return jsonify({
            "success": True,
            "api_key": temp_api_key,
            "company_id": company_id,
            "temporary": True,
            "message": "Temporary API key provided"
        })

@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    email = data.get("user_email")
    password = data.get("password")
    user_name = data.get("user_name")
    company_name = data.get("company_name")
    otp = data.get("otp")  # New field for OTP verification

    if not email or not password or not user_name or not company_name:
        return jsonify({"error": "user_email, user_name, company_name and password are required"}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "Invalid email format"}), 400

    if User.query.filter_by(user_email=email).first():
        return jsonify({"error": "User already exists"}), 400

    try:
        # If OTP is provided, verify it
        if otp:
            if not verify_otp(email, otp):
                return jsonify({"error": "Invalid or expired OTP"}), 400
        else:
            # Send verification email with OTP
            success, otp = send_verification_email(email)
            if not success:
                # For development, we'll bypass email verification
                # In production, you should return an error
                current_app.logger.warning("Email service failed, bypassing verification for development")
                # Create user without verification
                user = User(
                    user_email=email,
                    user_name=user_name,
                    company_name=company_name,
                    is_verified=True
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()

                # Generate JWT token
                token = generate_jwt({"user_id": user.id, "company_id": user.company_id})

                response = make_response(jsonify({
                    "message": "User registered successfully (email verification bypassed)",
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
                    secure=False,  # Changed to False for development
                    samesite="Lax"
                )
                return response
            return jsonify({"message": "Verification OTP sent to your email"}), 200

        # Create new user
        user = User(
            user_email=email,
            user_name=user_name,
            company_name=company_name,
            is_verified=True  # Set to True after OTP verification
        )
        user.set_password(password)
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
            secure=False,  # Changed to False for development
            samesite="Lax"
        )
        return response
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration failed: {str(e)}")
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
    try:
        data = request.get_json()
        email = data.get('user_email')
        password = data.get('password')
        remember_me = data.get('remember_me', False)

        if not email or not password:
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required',
                'user': None
            }), 400

        # Find user by email
        user = User.query.filter_by(user_email=email).first()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'Invalid email or password',
                'user': None
            }), 401

        # Check password
        if not check_password_hash(user.password_hash, password):
            return jsonify({
                'status': 'error',
                'message': 'Invalid email or password',
                'user': None
            }), 401

        # Generate token with a proper dictionary payload
        token_payload = {
            "user_id": user.id
        }
        
        # Add company_id if available
        if user.company_id:
            token_payload["company_id"] = user.company_id
            
        token = generate_jwt(token_payload)

        # Create user data for response
        user_data = {
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

        # Create response
        response = make_response(jsonify({
            'status': 'success',
            'message': 'Login successful',
            'user': user_data,
            'token': token
        }), 200)
        
        # Set cookie with more consistent and secure settings
        # Default cookie expiry to 24 hours if remember_me is not specified
        max_age = 30 * 24 * 60 * 60 if remember_me else 24 * 60 * 60  # 30 days if remember_me, else 24 hours
        
        # Set the cookie with explicit domain to current host
        response.set_cookie(
            "access_token", 
            token,
            max_age=max_age,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="Lax",  # Lax permits cookies during navigation, Strict would block them
            path="/"  # Available across all paths
        )
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Login failed: {str(e)}',
            'user': None
        }), 500

@users_bp.route('/logout', methods=['POST'])
def logout():
    try:
        response = make_response(jsonify({
            "status": "success",
            "message": "Logged out successfully"
        }), 200)
        
        # Ensure cookie is properly invalidated with consistent settings
        response.set_cookie(
            "access_token", "",
            max_age=0,  # Expire immediately
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="Lax",
            path="/"  # Match the path used in login
        )
        return response
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Logout failed: {str(e)}"
        }), 500

@users_bp.route('/profile', methods=['GET'])
def profile():
    try:
        token = get_token_from_request()
        if not token:
            return jsonify({
                "status": "error", 
                "message": "Token missing",
                "user": None
            }), 401

        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                "status": "error", 
                "message": "Invalid or expired token",
                "user": None
            }), 401

        # Get user_id from the payload dictionary
        user_id = payload.get("user_id")
        if not user_id:
            return jsonify({
                "status": "error", 
                "message": "Invalid token format - missing user_id",
                "user": None
            }), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({
                "status": "error", 
                "message": "User not found",
                "user": None
            }), 404

        # Check if company_logo exists
        logo_url = user.company_logo
        if logo_url and not os.path.exists(os.path.join(current_app.root_path, logo_url.lstrip('/'))):
            # If logo file doesn't exist but URL is in database, generate a default avatar URL
            logo_url = f"https://ui-avatars.com/api/?name={user.company_name or 'Company'}&background=random"
            # Optional: Update the database to avoid future 404s
            user.company_logo = None
            db.session.commit()

        # Create a user data object
        user_data = {
            "id": user.id,
            "user_name": user.user_name,
            "user_phone": user.user_phone,
            "user_email": user.user_email,
            "company_id": user.company_id,
            "company_name": user.company_name,
            "company_phone": user.company_phone,
            "business_address": user.business_address,
            "company_website": user.company_website,
            "company_logo": logo_url,
            "niche": user.niche,
            "subscription_plan": user.subscription_plan,
            "is_verified": user.is_verified,
            "created_at": user.created_at.isoformat(),
            "role": "Member"  # Hardcode role instead of accessing user.role
        }
            
        # Add subscription_expires_at if it exists
        if hasattr(user, 'subscription_expires_at') and user.subscription_expires_at:
            user_data["subscription_expires_at"] = user.subscription_expires_at.isoformat()
        else:
            user_data["subscription_expires_at"] = None

        return jsonify({
            "status": "success",
            "message": "Profile retrieved successfully",
            "user": user_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Profile retrieval error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to retrieve profile: {str(e)}",
            "user": None
        }), 500

@users_bp.route('/upload_logo', methods=['POST'])
def upload_logo():
    try:
        token = get_token_from_request()
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        # Get user from token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user_id = payload.get("user_id")
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404

        if 'logo' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        logo_file = request.files['logo']
        if logo_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        if not '.' in logo_file.filename or \
           logo_file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed types: PNG, JPG, JPEG, GIF'}), 400

        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Generate unique filename with user ID
        filename = f"user_{user_id}_{uuid.uuid4().hex}.{logo_file.filename.rsplit('.', 1)[1].lower()}"
        filepath = os.path.join(uploads_dir, filename)

        # Save the file
        logo_file.save(filepath)

        # Update user's company_logo in the database
        logo_url = f"/static/uploads/{filename}"
        user.company_logo = logo_url
        db.session.commit()

        return jsonify({
            'message': 'Logo uploaded successfully',
            'user': {
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
        return jsonify({'error': str(e)}), 500

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

def chatbot_to_dict(chatbot):
    """
    Convert a ChatbotConfig object to a dictionary for API responses.
    """
    return {
        "id": chatbot.id,
        "company_id": chatbot.company_id,
        "bot_name": chatbot.bot_name,
        "purpose": chatbot.purpose,
        "goal": chatbot.goal,
        "role": chatbot.role,
        "subscription_plan": chatbot.subscription_plan if hasattr(chatbot, "subscription_plan") else None,
        "version": chatbot.version,
        "last_trained_at": chatbot.last_trained_at.isoformat() if chatbot.last_trained_at else None
    }

@users_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    """
    Get dashboard data for the current user.
    Returns:
        - User information
        - Chatbot statistics
        - Chatbot list
        - Subscription information
    """
    # Get company_id from token
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code
    
    # Get user info
    from users.models import User
    user = User.query.filter_by(company_id=company_id).first()
    
    user_info = {
        "name": user.user_name,
        "email": user.user_email,
        "plan": user.subscription_plan or "Free Plan"
    }
    
    # Get chatbots
    chatbots = ChatbotConfig.query.filter_by(company_id=company_id).all()
    chatbot_list = [chatbot_to_dict(chatbot) for chatbot in chatbots]
    
    # Get stats
    stats = {}
    
    # Chatbot count
    stats["chatbotCount"] = len(chatbots)
    
    # Total messages
    chatbot_ids = [chatbot.id for chatbot in chatbots]
    if chatbot_ids:
        # Get all chat sessions for these chatbots
        sessions = ChatSession.query.join(
            ChatbotConfig, ChatSession.chatbot_id == ChatbotConfig.id
        ).filter(ChatbotConfig.id.in_(chatbot_ids)).all()
        
        session_ids = [session.id for session in sessions]
        if session_ids:
            # Count messages
            message_count = ChatMessage.query.filter(
                ChatMessage.session_id.in_(session_ids)
            ).count()
            stats["messageCount"] = message_count
        else:
            stats["messageCount"] = 0
    else:
        stats["messageCount"] = 0
    
    # Subscription expiry
    if user.subscription_expires_at:
        today = datetime.utcnow().date()
        days_remaining = (user.subscription_expires_at.date() - today).days
        
        if days_remaining > 0:
            stats["subscriptionExpiry"] = f"{days_remaining} days" 
        else:
            stats["subscriptionExpiry"] = "Expired"
    else:
        stats["subscriptionExpiry"] = "Not subscribed"
    
    # Get recent activity
    recent_activity = []
    if session_ids:
        # Get last 10 messages with their sessions
        recent_messages = ChatMessage.query.filter(
            ChatMessage.session_id.in_(session_ids)
        ).order_by(ChatMessage.timestamp.desc()).limit(10).all()
        
        # Organize by session
        for message in recent_messages:
            session = next((s for s in sessions if s.id == message.session_id), None)
            if not session:
                continue
                
            chatbot = next((c for c in chatbots if c.id == session.chatbot_id), None)
            if not chatbot:
                continue
                
            recent_activity.append({
                "timestamp": message.timestamp.isoformat(),
                "message": message.message[:100] + "..." if len(message.message) > 100 else message.message,
                "sender": message.sender,
                "chatbotName": chatbot.bot_name,
                "chatbotId": chatbot.id
            })
    
    return jsonify({
        "user": user_info,
        "stats": stats,
        "chatbots": chatbot_list,
        "recentActivity": recent_activity
    }), 200

@users_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        email = data.get("email")
        if not email:
            return jsonify({"error": "Email is required"}), 400

        user = User.query.filter_by(user_email=email).first()
        if not user:
            # For security, we return success even if email doesn't exist
            return jsonify({"message": "If your email is registered, you will receive a password reset link"}), 200

        # Generate reset token
        reset_token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(seconds=PASSWORD_RESET_EXPIRY)
        }, PASSWORD_RESET_SECRET, algorithm='HS256')

        # Send reset email
        success = send_password_reset_email(email, reset_token)
        if not success:
            return jsonify({"error": "Failed to send reset email"}), 500

        return jsonify({"message": "Password reset link sent to your email"}), 200
    except Exception as e:
        current_app.logger.error(f"Forgot password error: {str(e)}")
        return jsonify({"error": "Failed to process request"}), 500

@users_bp.route('/reset-password', methods=['GET'])
def serve_reset_password():
    return current_app.send_static_file('reset-password.html')

@users_bp.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        token = data.get("token")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if not all([token, new_password, confirm_password]):
            return jsonify({"error": "Token, new password, and confirm password are required"}), 400

        if new_password != confirm_password:
            return jsonify({"error": "Passwords do not match"}), 400

        try:
            payload = jwt.decode(token, PASSWORD_RESET_SECRET, algorithms=['HS256'])
            user_id = payload.get('user_id')
            if not user_id:
                return jsonify({"error": "Invalid token"}), 400

            user = User.query.get(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404

            user.set_password(new_password)
            db.session.commit()
            return jsonify({"message": "Password reset successfully"}), 200

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Reset link has expired"}), 400
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid reset link"}), 400

    except Exception as e:
        current_app.logger.error(f"Reset password error: {str(e)}")
        return jsonify({"error": "Failed to reset password"}), 500

@users_bp.route('/create-api-key', methods=['POST'])
def create_api_key():
    """
    Create a new API key for the company.
    This endpoint is used by the dashboard to create API keys.
    """
    logger = logging.getLogger(__name__)
    logger.info("Creating new API key")
    
    # Get the company ID from the JWT token or session
    try:
        company_id, error_response, status_code = get_logged_in_company_id()
        if error_response:
            return error_response, status_code
    except Exception as auth_err:
        logger.error(f"Authentication error: {str(auth_err)}", exc_info=True)
        return jsonify({"error": "Authentication error", "success": False}), 401
    
    if not company_id:
        logger.error("No company ID found in token or session")
        return jsonify({"error": "No company ID found", "success": False}), 404
    
    try:
        # Generate a new API key with a secure random string
        api_key = f"sk_{secrets.token_hex(24)}"
        
        # Create a new ApiKey record
        try:
            # Use SQLAlchemy Core for more direct control
            from sqlalchemy import text
            
            # Insert the new API key using SQL to avoid ORM issues
            sql = text("""
                INSERT INTO api_keys (company_id, key, status, created_at, subscription_plan)
                VALUES (:company_id, :key, 'active', NOW(), :subscription_plan)
                RETURNING id
            """)
            
            # Get the user's subscription plan
            user = User.query.get(company_id)
            subscription_plan = user.subscription_plan or 'basic'
            
            result = db.session.execute(sql, {
                "company_id": company_id,
                "key": api_key,
                "subscription_plan": subscription_plan
            })
            
            # Get the ID of the new API key
            api_key_id = result.scalar()
            
            # Commit the transaction
            db.session.commit()
            
            logger.info(f"API key created successfully for company ID: {company_id}")
            
            # Return the new API key
            return jsonify({
                "success": True,
                "api_key": api_key,
                "company_id": company_id,
                "api_key_id": api_key_id
            })
        except Exception as db_err:
            db.session.rollback()
            logger.error(f"Database error: {str(db_err)}", exc_info=True)
            return jsonify({
                "success": False,
                "error": f"Database error: {str(db_err)}",
                "company_id": company_id
            }), 500
    except Exception as e:
        logger.error(f"Error creating API key: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Error creating API key: {str(e)}",
            "company_id": company_id
        }), 500
