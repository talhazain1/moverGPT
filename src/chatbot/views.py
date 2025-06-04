# chatbot/views.py

import os
import json
import csv
import uuid
import openai
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from sqlalchemy.orm.attributes import flag_modified
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import logging
from sqlalchemy import func
from functools import wraps

from core.database import db
from core.utils import verify_jwt
from users.models import User
from chatbot.models import ChatbotConfig, ChatSession, ChatMessage
from chatbot.model_training import train_model
from chatbot.model_inference import run_inference_openai
from subscriptions.decorators import require_feature
from subscriptions.features import Feature, SubscriptionPlan, get_available_features
from companies.models import Company, MovingParameters

# Define blueprints.
chatbot_bp = Blueprint('chatbot', __name__)
admin_chatbots_bp = Blueprint("admin_chatbots", __name__)
admin_bp = Blueprint("admin", __name__)

# Add JSONP support for cross-domain requests
def jsonp(func):
    """Wraps JSONified output for JSONP requests."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            data = func(*args, **kwargs).data
            content = f"{callback}({data.decode('utf-8')});"
            return current_app.response_class(
                content, mimetype='application/javascript')
        else:
            return func(*args, **kwargs)
    return decorated_function

# Define the upload folder path
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'knowledge_base'))

# Make sure the uploads directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

###############################################
# Helper Functions
###############################################

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

    from users.models import User
    user = User.query.get(payload.get("user_id"))
    if not user:
        return None, jsonify({"error": "User not found"}), 404
    # Return company_id if available; otherwise fallback to user.id.
    return user.company_id or user.id, None, None

def chatbot_to_dict(chatbot: ChatbotConfig) -> dict:
    # Map the subscription_plan field.
    subscription_plan = chatbot.subscription_plan if hasattr(chatbot, "subscription_plan") else None
    return {
        "company_id": chatbot.company_id,
        "id": chatbot.id,
        "chatbot_id": chatbot.chatbot_id,
        "bot_name": chatbot.bot_name,
        "purpose": chatbot.purpose,
        "goal": chatbot.goal,
        "role": chatbot.role,
        "subscription_plan": subscription_plan,
        "configuration": chatbot.configuration,
        "knowledge_base": chatbot.knowledge_base,
        "version": chatbot.version,
        "last_trained_at": chatbot.last_trained_at.isoformat() if chatbot.last_trained_at else None
    }

###############################################
# 1. Chat Session Endpoints
###############################################

@chatbot_bp.route('/jsonp/session', methods=['GET'])
@jsonp
def create_jsonp_session():
    """JSONP endpoint for creating a chat session to avoid CORS issues"""
    try:
        print("DEBUG: Entered create_jsonp_session")
        
        # Parse optional chatbotId and companyId, converting to int
        chatbot_id_raw = request.args.get('chatbotId')
        try:
            chatbot_id = int(chatbot_id_raw) if chatbot_id_raw is not None else None
        except ValueError:
            chatbot_id = None
        company_id_raw = request.args.get('companyId')
        try:
            company_id = int(company_id_raw) if company_id_raw is not None else None
        except ValueError:
            company_id = None

        # Attempt JWT authentication first
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # Allow JWT via query param for JSONP
            token = request.args.get('token') or request.cookies.get('access_token') or request.cookies.get('permanent_token')
        payload = None
        if token:
            payload = verify_jwt(token)
        if payload:
            # Authenticated via JWT
            user_id = payload.get('user_id')
            print(f"DEBUG: JWT auth used for session creation, user_id={user_id}")
        else:
            # Attempt embed bypass via companyId param
            if company_id:
                print(f"DEBUG: Bypassing auth for embed, using numeric companyId as user_id={company_id}")
                user_id = int(company_id)
            else:
                # Fallback to API key authentication
                api_key = request.args.get('apiKey')
                print(f"DEBUG: JSONP session creation params: apiKey={api_key}, chatbotId={chatbot_id}, companyId={company_id}")
                if not api_key:
                    print("DEBUG: No API key or JWT provided in JSONP session creation and no companyId to bypass")
                    resp = jsonify({"status": "error", "message": "Authentication required"})
                    resp.status_code = 401
                    return resp
                from admin.models import ApiKey
                api_key_obj = ApiKey.query.filter_by(key=api_key, status='active').first()
                if not api_key_obj:
                    print("DEBUG: Invalid API key in JSONP session creation")
                    resp = jsonify({"status": "error", "message": "Invalid API key"})
                    resp.status_code = 401
                    return resp
                user_id = f"api_key_user_{api_key_obj.company_id}"
                api_key_obj.last_used_at = datetime.utcnow()
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    print("DEBUG: Error updating last_used_at for API key")
        
        # Create session object
        session_obj = ChatSession(user_id=user_id)
        
        # Set chatbot_id if provided
        if chatbot_id:
            # Verify chatbot exists
            chatbot = ChatbotConfig.query.get(chatbot_id)
            if not chatbot:
                print(f"DEBUG: Chatbot with ID {chatbot_id} not found")
                resp = jsonify({
                    "status": "error",
                    "message": f"Chatbot with ID {chatbot_id} not found"
                })
                resp.status_code = 404
                return resp
            
            session_obj.chatbot_id = chatbot_id
            session_obj.bot_name = chatbot.bot_name or f"Chatbot {chatbot_id}"  # Ensure bot_name is never None
        else:
            # If no chatbot_id provided, try to find the default chatbot for the company from param
            if company_id:
                chatbot = ChatbotConfig.query.filter_by(company_id=company_id).first()
                if chatbot:
                    session_obj.chatbot_id = chatbot.id
                    session_obj.bot_name = chatbot.bot_name or f"Chatbot {chatbot.id}"
            # If still no chatbot_id, fallback to the API key's company
            if not session_obj.chatbot_id:
                api_company_id = api_key_obj.company_id
                chatbot = ChatbotConfig.query.filter_by(company_id=api_company_id).first()
                if chatbot:
                    session_obj.chatbot_id = chatbot.id
                    session_obj.bot_name = chatbot.bot_name or f"Chatbot {chatbot.id}"
        
        try:
            db.session.add(session_obj)
            db.session.commit()
            print("DEBUG: Created ChatSession with id=", session_obj.id)
            return jsonify({
                "status": "success",
                "message": "Chat session created successfully",
                "session_id": session_obj.id,
                "created_at": session_obj.created_at.isoformat()
            })
        except Exception as e:
            db.session.rollback()
            print("DEBUG: Failed to create session:", e)
            return jsonify({
                "status": "error",
                "message": f"Failed to create session: {e}"
            })
    except Exception as e:
        current_app.logger.exception("Exception in create_jsonp_session")
        # Return JSONP error response if callback is present
        resp = jsonify({"status": "error", "message": "Internal server error"})
        resp.status_code = 500
        return resp

@chatbot_bp.route('/session', methods=['POST'])
def create_chat_session():
    print("DEBUG: Entered create_chat_session")
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in create_chat_session")
        return jsonify({"error": "Authorization header missing"}), 401

    token = auth_header.split(" ")[-1]
    
    # First try to validate as JWT token
    payload = verify_jwt(token)
    
    # If not a valid JWT, check if it's an API key
    if not payload:
        print("DEBUG: Not a valid JWT token, checking if it's an API key")
        # Check if the token is an API key
        from admin.models import ApiKey
        api_key = ApiKey.query.filter_by(key=token, status='active').first()
        
        if api_key:
            print(f"DEBUG: Valid API key found for company_id {api_key.company_id}")
            # Create a user_id from the company_id for API key auth
            user_id = f"api_key_user_{api_key.company_id}"
            company_id = api_key.company_id
            
            # Update last_used_at timestamp
            api_key.last_used_at = datetime.utcnow()
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"DEBUG: Error updating last_used_at for API key: {e}")
        else:
            print("DEBUG: Invalid or expired token/API key")
            return jsonify({
                "status": "error",
                "message": "Invalid or expired token or API key"
            }), 200  # Return 200 to prevent redirect issues
    else:
        # Valid JWT token
        user_id = payload.get("user_id")
        if not user_id:
            print("DEBUG: No user_id in token")
            return jsonify({
                "status": "error",
                "message": "No user_id found in token"
            }), 400
        company_id = None  # Will be set from the request data

    # Get optional chatbot_id from request
    data = request.get_json() or {}
    chatbot_id = data.get("chatbot_id")
    
    # Create session object
    session_obj = ChatSession(user_id=user_id)
    
    # Set chatbot_id if provided
    if chatbot_id:
        # Verify chatbot exists
        chatbot = ChatbotConfig.query.get(chatbot_id)
        if not chatbot:
            print(f"DEBUG: Chatbot with ID {chatbot_id} not found")
            return jsonify({
                "status": "error",
                "message": f"Chatbot with ID {chatbot_id} not found"
            }), 404
        
        session_obj.chatbot_id = chatbot_id
        session_obj.bot_name = chatbot.bot_name or f"Chatbot {chatbot_id}"  # Ensure bot_name is never None
    else:
        # If no chatbot_id provided, try to find the default chatbot for the company
        if company_id:
            chatbot = ChatbotConfig.query.filter_by(company_id=company_id).first()
            if chatbot:
                session_obj.chatbot_id = chatbot.id
                session_obj.bot_name = chatbot.bot_name or f"Chatbot {chatbot.id}"  # Ensure bot_name is never None
    
    try:
        db.session.add(session_obj)
        db.session.commit()
        print("DEBUG: Created ChatSession with id=", session_obj.id)
        return jsonify({
            "status": "success",
            "message": "Chat session created successfully",
            "session_id": session_obj.id,
            "created_at": session_obj.created_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to create session:", e)
        return jsonify({
            "status": "error",
            "message": f"Failed to create session: {e}"
        }), 500

@chatbot_bp.route('/session/<int:session_id>/message', methods=['POST'])
def add_chat_message(session_id):
    print("DEBUG: Entered add_chat_message, session_id=", session_id)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in add_chat_message")
        return jsonify({"error": "Authorization header missing"}), 401

    token = auth_header.split(" ")[-1]
    
    # First try to validate as JWT token
    payload = verify_jwt(token)
    
    # If not a valid JWT, check if it's an API key
    if not payload:
        print("DEBUG: Not a valid JWT token in add_chat_message, checking if it's an API key")
        # Check if the token is an API key
        from admin.models import ApiKey
        api_key = ApiKey.query.filter_by(key=token, status='active').first()
        
        if api_key:
            print(f"DEBUG: Valid API key found for company_id {api_key.company_id} in add_chat_message")
            # Update last_used_at timestamp
            api_key.last_used_at = datetime.utcnow()
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"DEBUG: Error updating last_used_at for API key: {e}")
        else:
            print("DEBUG: Invalid or expired token/API key in add_chat_message")
            return jsonify({"error": "Invalid or expired token or API key"}), 401

    data = request.get_json() or {}
    sender = data.get("sender")
    message_text = data.get("message")
    if not sender or not message_text:
        print("DEBUG: Missing sender or message in add_chat_message")
        return jsonify({"error": "sender and message are required"}), 400
    if sender not in ["user", "bot"]:
        print("DEBUG: Invalid sender in add_chat_message:", sender)
        return jsonify({"error": "Invalid sender; must be 'user' or 'bot'"}), 400

    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print("DEBUG: Chat session not found, id=", session_id)
        return jsonify({"error": "Chat session not found"}), 404

    new_msg = ChatMessage(session_id=session_id, sender=sender, message=message_text)
    try:
        db.session.add(new_msg)
        db.session.commit()
        print("DEBUG: Added new message with id=", new_msg.id)
        return jsonify({
            "message": "Message added",
            "message_id": new_msg.id,
            "timestamp": new_msg.timestamp.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to add message:", e)
        return jsonify({"error": f"Failed to add message: {e}"}), 500

@chatbot_bp.route('/session/<int:session_id>/messages', methods=['GET'])
def get_chat_messages(session_id):
    print("DEBUG: Entered get_chat_messages, session_id=", session_id)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in get_chat_messages")
        return jsonify({"error": "Authorization header missing"}), 401

    token = auth_header.split(" ")[-1]
    
    # First try to validate as JWT token
    payload = verify_jwt(token)
    
    # If not a valid JWT, check if it's an API key
    if not payload:
        print("DEBUG: Not a valid JWT token in get_chat_messages, checking if it's an API key")
        # Check if the token is an API key
        from admin.models import ApiKey
        api_key = ApiKey.query.filter_by(key=token, status='active').first()
        
        if api_key:
            print(f"DEBUG: Valid API key found for company_id {api_key.company_id} in get_chat_messages")
            # Update last_used_at timestamp
            api_key.last_used_at = datetime.utcnow()
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"DEBUG: Error updating last_used_at for API key: {e}")
        else:
            print("DEBUG: Invalid or expired token/API key in get_chat_messages")
            return jsonify({"error": "Invalid or expired token or API key"}), 401

    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print("DEBUG: Chat session not found, id=", session_id)
        return jsonify({"error": "Chat session not found"}), 404

    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    msg_list = [{
        "id": m.id,
        "sender": m.sender,
        "message": m.message,
        "timestamp": m.timestamp.isoformat()
    } for m in messages]
    print("DEBUG: Returning", len(msg_list), "messages")
    return jsonify({"status": "success", "session_id": session_id, "messages": msg_list}), 200

@chatbot_bp.route('/jsonp/session/<int:session_id>/messages', methods=['GET'])
@jsonp
def get_jsonp_chat_messages(session_id):
    """JSONP endpoint for fetching chat messages to avoid CORS issues"""
    print("DEBUG: Entered get_jsonp_chat_messages, session_id=", session_id)
    
    # Attempt JWT authentication first
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Allow JWT via query param for JSONP
        token = request.args.get('token') or request.cookies.get('access_token') or request.cookies.get('permanent_token')
    payload = None
    if token:
        payload = verify_jwt(token)
    if payload:
        print(f"DEBUG: JWT auth used for JSONP get messages, user_id={payload.get('user_id')}")
    else:
        # Fallback to API key authentication
        api_key = request.args.get('apiKey')
        if not api_key:
            print("DEBUG: No API key or JWT provided in JSONP get messages")
            return jsonify({"status": "error", "message": "Authentication required"})
        from admin.models import ApiKey
        api_key_obj = ApiKey.query.filter_by(key=api_key, status='active').first()
        if not api_key_obj:
            print("DEBUG: Invalid API key in JSONP get messages")
            return jsonify({"status": "error", "message": "Invalid API key"})
        api_key_obj.last_used_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            print("DEBUG: Error updating last_used_at for API key")
    
    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print("DEBUG: Chat session not found in JSONP get messages, id=", session_id)
        return jsonify({
            "status": "error",
            "message": "Chat session not found"
        })

    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    msg_list = [{
        "id": m.id,
        "sender": m.sender,
        "message": m.message,
        "timestamp": m.timestamp.isoformat()
    } for m in messages]
    print("DEBUG: Returning", len(msg_list), "messages from JSONP endpoint")
    return jsonify({
        "status": "success", 
        "session_id": session_id, 
        "messages": msg_list
    })

@chatbot_bp.route('/session/<int:session_id>/end', methods=['POST'])
def end_chat_session(session_id):
    print("DEBUG: Entered end_chat_session, session_id=", session_id)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in end_chat_session")
        return jsonify({"error": "Authorization header missing"}), 401
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in end_chat_session")
        return jsonify({"error": "Invalid or expired token"}), 401
    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print("DEBUG: Chat session not found in end_chat_session")
        return jsonify({"error": "Chat session not found"}), 404
    session_obj.ended = True
    session_obj.updated_at = datetime.utcnow()
    try:
        db.session.commit()
        print("DEBUG: Ended chat session successfully, session_id=", session_id)
        return jsonify({"message": "Chat session ended"}), 200
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to end session:", e)
        return jsonify({"error": f"Failed to end session: {e}"}), 500

# List all chat sessions for the current user's company or API key
@chatbot_bp.route('/sessions', methods=['GET'])
def list_chat_sessions():
    # Determine company_id via JWT token, then API key, then Flask-Login session
    company_id = None
    # JWT auth
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
    else:
        token = request.cookies.get('access_token') or request.cookies.get('permanent_token')
    if token:
        payload = verify_jwt(token)
        if payload:
            company_id = payload.get('company_id') or payload.get('user_id')
    # API key fallback
    if not company_id:
        api_key = request.args.get('apiKey')
        if api_key:
            # Try admin model
            try:
                from admin.models import ApiKey as AdminApiKey
                key_obj = AdminApiKey.query.filter_by(key=api_key, status='active').first()
            except ImportError:
                key_obj = None
            # Try api_keys model
            if not key_obj:
                try:
                    from api_keys.models import ApiKey as APIKeysModel
                    key_obj = APIKeysModel.query.filter_by(key=api_key, status='active').first()
                except ImportError:
                    key_obj = None
            if not key_obj:
                return jsonify({'error': 'Authentication required'}), 401
            company_id = key_obj.company_id
    # Session fallback
    if not company_id:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        company_id = current_user.company_id
    # find all chatbots for this company
    bots = ChatbotConfig.query.filter_by(company_id=company_id).all()
    bot_ids = [b.id for b in bots]
    sessions = ChatSession.query.filter(ChatSession.chatbot_id.in_(bot_ids)) \
                                .order_by(ChatSession.created_at.desc()) \
                                .all()
    result = []
    for s in sessions:
        first = ChatMessage.query.filter_by(session_id=s.id, sender='user') \
                                  .order_by(ChatMessage.timestamp.asc()).first()
        result.append({
            'session_id': s.id,
            'category': s.category.name if s.category else None,
            'first_message': first.message if first else '',
            'created_at': s.created_at.isoformat()
        })
    return jsonify(result), 200

# Retrieve full conversation and user details for one session via API key or JWT
@chatbot_bp.route('/session/<int:session_id>/details', methods=['GET'])
def get_session_details(session_id):
    # Determine company_id via JWT token, then API key, then Flask-Login session
    company_id = None
    # JWT auth
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
    else:
        token = request.cookies.get('access_token') or request.cookies.get('permanent_token')
    if token:
        payload = verify_jwt(token)
        if payload:
            company_id = payload.get('company_id') or payload.get('user_id')
    # API key fallback
    if not company_id:
        api_key = request.args.get('apiKey')
        if api_key:
            try:
                from admin.models import ApiKey as AdminApiKey
                key_obj = AdminApiKey.query.filter_by(key=api_key, status='active').first()
            except ImportError:
                key_obj = None
            if not key_obj:
                try:
                    from api_keys.models import ApiKey as APIKeysModel
                    key_obj = APIKeysModel.query.filter_by(key=api_key, status='active').first()
                except ImportError:
                    key_obj = None
            if not key_obj:
                return jsonify({'error': 'Authentication required'}), 401
            company_id = key_obj.company_id
    # Session fallback
    if not company_id:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        company_id = current_user.company_id
    # Fetch session and verify ownership
    sess = ChatSession.query.get_or_404(session_id)
    chatbot_obj = ChatbotConfig.query.get(sess.chatbot_id)
    if not chatbot_obj or chatbot_obj.company_id != company_id:
        return jsonify({'error': 'Forbidden'}), 403
    ud = sess.user_details
    user_details = {
        'name': ud.name,
        'email': ud.email,
        'phone': ud.phone,
        'origin': ud.origin,
        'destination': ud.destination,
        'move_size': ud.move_size,
        'move_date': ud.move_date.isoformat() if ud.move_date else None,
        'services': ud.services
    } if ud else None
    messages = ChatMessage.query.filter_by(session_id=session_id) \
                                .order_by(ChatMessage.timestamp.asc()).all()
    msgs = [{'sender': m.sender, 'message': m.message, 'timestamp': m.timestamp.isoformat()} for m in messages]
    return jsonify({
        'session_id': session_id,
        'category': sess.category.name if sess.category else None,
        'user_details': user_details,
        'messages': msgs
    }), 200

###############################################
# 2. Inference with Auto-Training and Message Storage
###############################################

# Import the direct_inference function from our fixed module
from chatbot.direct_inference_fixed import direct_inference as direct_inference_handler

@chatbot_bp.route('/direct/inference', methods=['GET'])
def direct_inference():
    """Direct API endpoint for chatbot inference with JSONP support"""
    return direct_inference_handler()

def create_jsonp_response(data, callback=None):
    """Create a JSONP response if callback is provided, otherwise return JSON"""
    if callback:
        json_data = json.dumps(data)
        return f"{callback}({json_data})", 200, {'Content-Type': 'application/javascript'}
    else:
        return jsonify(data)

@chatbot_bp.route('/jsonp/inference', methods=['GET'])
@jsonp
def jsonp_chatbot_inference():
    """JSONP endpoint for chatbot inference to avoid CORS issues"""
    current_app.logger.info("Entered jsonp_chatbot_inference")
    try:
        # Get parameters from query string
        api_key = request.args.get('apiKey')
        session_id = request.args.get('sessionId')
        message = request.args.get('message')
        company_id = request.args.get('companyId')
        website_url = request.args.get('websiteUrl')
        
        if not api_key:
            current_app.logger.warning("No API key provided in JSONP inference")
            return jsonify({
                "status": "error",
                "message": "API key is required",
                "response": "I'm sorry, authentication is required to use this service."
            })
        
        # Check if the API key is valid
        from admin.models import ApiKey
        api_key_obj = ApiKey.query.filter_by(key=api_key, status='active').first()
        
        if not api_key_obj:
            current_app.logger.warning("Invalid API key in JSONP inference")
            return jsonify({
                "status": "error",
                "message": "Invalid API key",
                "response": "I'm sorry, your API key is invalid or has expired."
            })
        
        # Update last_used_at timestamp
        api_key_obj.last_used_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating last_used_at for API key: {e}")
        
        if not company_id or not message:
            current_app.logger.warning("Missing company_id or message in JSONP inference")
            return jsonify({
                "status": "error",
                "message": "Missing required fields",
                "response": "Please provide both company_id and message"
            })

        # Find the chatbot for the company
        chatbot_config = ChatbotConfig.query.filter_by(company_id=company_id).first()
        if not chatbot_config:
            current_app.logger.warning(f"No chatbot found for company_id={company_id} in JSONP inference")
            return jsonify({
                "status": "error",
                "message": f"No chatbot found for company_id={company_id}",
                "response": "Sorry, no chatbot is configured for this company."
            })
        
        # Create a new session if none is provided
        if not session_id:
            current_app.logger.info("No session_id provided in JSONP inference. Creating new session.")
            user_id = f"api_key_user_{api_key_obj.company_id}"
            new_session = ChatSession(user_id=user_id, chatbot_id=chatbot_config.id)
            try:
                db.session.add(new_session)
                db.session.commit()
                session_id = new_session.id
                current_app.logger.info(f"Created new session with id={session_id} in JSONP inference")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to create new session in JSONP inference: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Failed to create session: {str(e)}",
                    "response": "Sorry, I encountered an error. Please try again later."
                })
        
        # Store the user message
        try:
            user_message = ChatMessage(session_id=session_id, sender="user", message=message)
            db.session.add(user_message)
            db.session.commit()
            current_app.logger.info(f"Stored user message in JSONP inference, id={user_message.id}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to store user message in JSONP inference: {str(e)}")
        
        # Run inference
        try:
            response_text = run_inference_openai(
                chatbot_config=chatbot_config,
                query=message,
                history=[],  # We'll get history from the session
                session_id=session_id
            )
            
            # Store the bot response
            bot_message = ChatMessage(session_id=session_id, sender="bot", message=response_text)
            db.session.add(bot_message)
            db.session.commit()
            current_app.logger.info(f"Stored bot response in JSONP inference, id={bot_message.id}")
            
            return jsonify({
                "status": "success",
                "message": "Inference completed successfully",
                "response": response_text,
                "session_id": session_id
            })
        except Exception as e:
            current_app.logger.error(f"Error in JSONP inference: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Error in inference: {str(e)}",
                "response": "Sorry, I encountered an error processing your request. Please try again later.",
                "session_id": session_id
            })
    except Exception as e:
        current_app.logger.error(f"Unexpected error in JSONP inference: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "response": "Sorry, an unexpected error occurred. Please try again later."
        })

@chatbot_bp.route('/inference', methods=['POST'])
def chatbot_inference():
    current_app.logger.info("Entered chatbot_inference")
    try:
        # Get token from cookies first, then header
        token = request.cookies.get('access_token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            current_app.logger.warning("No authentication token provided")
            return jsonify({
                "status": "error",
                "message": "Authentication required",
                "response": "I'm sorry, you need to be logged in to use this service."
            }), 200  # Return 200 to prevent redirect issues
        
        # First try to validate as JWT token
        payload = verify_jwt(token)
        
        # If not a valid JWT, check if it's an API key
        if not payload:
            current_app.logger.info("Not a valid JWT token in chatbot_inference, checking if it's an API key")
            # Check if the token is an API key
            from admin.models import ApiKey
            api_key = ApiKey.query.filter_by(key=token, status='active').first()
            
            if api_key:
                current_app.logger.info(f"Valid API key found for company_id {api_key.company_id} in chatbot_inference")
                # Create a payload with company_id for API key auth
                payload = {"company_id": api_key.company_id}
                
                # Update last_used_at timestamp
                api_key.last_used_at = datetime.utcnow()
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error updating last_used_at for API key: {e}")
            else:
                current_app.logger.warning("Invalid or expired token/API key")
                return jsonify({
                    "status": "error",
                    "message": "Invalid or expired token or API key",
                    "response": "Your session has expired or your API key is invalid. Please try again."
                }), 200  # Return 200 to prevent redirect issues
            
        data = request.get_json() or {}
        company_id = data.get("company_id")
        query = data.get("query")
        session_id = request.args.get("session_id") or data.get("session_id")
        
        # Get history from the request if provided
        history = data.get("history", [])
        
        if not company_id or not query:
            current_app.logger.warning("Missing company_id or query")
            return jsonify({
                "status": "error",
                "message": "Missing required fields",
                "response": "Please provide both company_id and query"
            }), 400

        # Find the chatbot for the company
        chatbot_config = ChatbotConfig.query.filter_by(company_id=company_id).first()
        if not chatbot_config:
            current_app.logger.warning(f"No chatbot found for company_id={company_id}")
            return jsonify({
                "status": "error",
                "message": f"No chatbot found for company_id={company_id}",
                "response": "Sorry, no chatbot is configured for this company."
            }), 404

        # Handle special welcome message query
        if query == "__WELCOME_MESSAGE__":
            current_app.logger.info("Special welcome message query detected")
            welcome_message = None
            
            # Try to get welcome message from configuration
            if chatbot_config.configuration and isinstance(chatbot_config.configuration, dict):
                welcome_message = chatbot_config.configuration.get("welcome_message")
            
            # Use default welcome message if none found
            if not welcome_message:
                welcome_message = f"Hello! I'm {chatbot_config.bot_name or 'an AI assistant'}. How can I help you today?"
                current_app.logger.info(f"Using default welcome message: {welcome_message}")
            
            # Create a new session if none is provided
            if not session_id:
                current_app.logger.info("No session_id provided for welcome message. Creating new session.")
                new_session = ChatSession(user_id=payload.get("user_id"), chatbot_id=chatbot_config.id)
                try:
                    db.session.add(new_session)
                    db.session.commit()
                    session_id = new_session.id
                    current_app.logger.info(f"Created new session with id={session_id} for welcome message")
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Failed to create new session for welcome message: {str(e)}")
                    # If we can't create a session, still return the welcome message
                    return jsonify({
                        "status": "success", 
                        "message": "Welcome message generated successfully",
                        "response": welcome_message
                    }), 200
            
            # Store the welcome message in the database
            try:
                bot_message = ChatMessage(session_id=session_id, sender="bot", message=welcome_message)
                db.session.add(bot_message)
                db.session.commit()
                current_app.logger.info(f"Stored welcome message, id={bot_message.id}")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to store welcome message: {str(e)}")
                # Continue and return the welcome message even if storing fails
                
            return jsonify({
                "status": "success",
                "message": "Welcome message generated successfully",
                "response": welcome_message,
                "session_id": session_id
            }), 200

        # If no trained model is present, auto-train the chatbot
        if not chatbot_config.trained_model:
            current_app.logger.info("No trained_model found. Automatically training now.")
            try:
                pickled_model = train_model(chatbot_config.knowledge_base or {}, chatbot_config.configuration or {})
                current_app.logger.info(f"Pickled model size (auto-trained): {len(pickled_model)} bytes")
                chatbot_config.trained_model = pickled_model
                chatbot_config.last_trained_at = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Automatic training failed: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": "Training failed",
                    "response": "I'm not trained yet. Please train me on a knowledge base.",
                    "session_id": session_id
                }), 200

        # Create a new session if none is provided
        if not session_id:
            current_app.logger.info("No session_id provided. Creating new session.")
            new_session = ChatSession(user_id=payload.get("user_id"), chatbot_id=chatbot_config.id)
            try:
                db.session.add(new_session)
                db.session.commit()
                session_id = new_session.id
                current_app.logger.info(f"Created new session with id={session_id}")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to create new session: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Failed to create new session: {str(e)}",
                    "response": "Sorry, I couldn't create a chat session. Please try again later."
                }), 500

        # Store the user's query as a message
        user_message = ChatMessage(session_id=session_id, sender="user", message=query)
        try:
            db.session.add(user_message)
            db.session.commit()
            current_app.logger.info(f"Stored user query message, id={user_message.id}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to store user message: {str(e)}")
            # Continue processing even if we fail to store the message

        # Process conversation history format if provided
        processed_history = []
        if history and isinstance(history, list):
            for i, msg in enumerate(history):
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    # Convert OpenAI format to our format
                    processed_history.append({
                        'sender': 'user' if msg['role'] == 'user' else 'bot',
                        'message': msg['content']
                    })
                    current_app.logger.debug(f"Converted history item {i}: {msg['role']} -> {processed_history[-1]['sender']}")
                elif isinstance(msg, dict) and 'sender' in msg and 'message' in msg:
                    # Our format
                    processed_history.append(msg)
                    current_app.logger.debug(f"Added history item {i} directly: {msg['sender']}")

        # Also fetch previous chat messages for this session if we don't have history
        try:
            if not processed_history and session_id:
                # Use the already imported ChatMessage from the top of the file
                previous_messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
                
                if previous_messages:
                    current_app.logger.info(f"Found {len(previous_messages)} previous messages for session {session_id}")
                    for msg in previous_messages:
                        processed_history.append({
                            'sender': msg.sender,
                            'message': msg.message
                        })
                        current_app.logger.debug(f"Added message from DB: {msg.sender}: {msg.message[:30]}...")
        except Exception as e:
            current_app.logger.error(f"Error fetching previous messages: {e}")

        # Check if this company is a moving company and if this is a moving-related query
        from chatbot.model_inference import is_moving_company, handle_moving_query

        if is_moving_company(company_id):
            # Try the moving chat handler first
            current_app.logger.info(f"Company {company_id} is a moving company, trying specialized handler")
            current_app.logger.info(f"Passing {len(processed_history)} history items to moving handler")
            moving_response = handle_moving_query(company_id, session_id, query, processed_history)
            if moving_response:
                # Moving chat handler provided a response, use it
                current_app.logger.info("Using response from moving handler")
                answer = moving_response
            else:
                # Not a moving query or moving handler couldn't process it, fall back to regular inference
                current_app.logger.info("Moving handler didn't provide a response, falling back to regular inference")
                try:
                    answer = run_inference_openai(chatbot_config, query, history=processed_history, top_n=3)
                except Exception as e:
                    current_app.logger.error(f"Inference error: {str(e)}")
                    return jsonify({
                        "status": "error",
                        "message": f"Inference error: {str(e)}",
                        "response": "Sorry, I encountered an error generating a response. Please try again later.",
                        "session_id": session_id
                    }), 200
        else:
            # Not a moving company, use regular inference
            try:
                answer = run_inference_openai(chatbot_config, query, history=processed_history, top_n=3)
            except Exception as e:
                current_app.logger.error(f"Inference error: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Inference error: {str(e)}",
                    "response": "Sorry, I encountered an error generating a response. Please try again later.",
                    "session_id": session_id
                }), 200

        # Store the bot's response as a message
        bot_message = ChatMessage(session_id=session_id, sender="bot", message=answer)
        try:
            db.session.add(bot_message)
            db.session.commit()
            current_app.logger.info(f"Stored bot answer message, id={bot_message.id}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to store bot message: {str(e)}")
            # Continue processing even if we fail to store the message

        current_app.logger.info("chatbot_inference returning answer")
        return jsonify({
            "status": "success",
            "message": "Response generated successfully",
            "response": answer,
            "session_id": session_id
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Unexpected error in chatbot_inference: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}",
            "response": "Sorry, something went wrong. Please try again later.",
            "session_id": session_id if 'session_id' in locals() else None
        }), 200

###############################################
# 3. Train / Retrain Endpoint
###############################################

@chatbot_bp.route('/train/<int:chatbot_id>', methods=['POST'])
def train_chatbot(chatbot_id):
    """Legacy training endpoint for backward compatibility.
    This redirects to the new /<chatbot_id>/train endpoint."""
    current_app.logger.info(f"Entered legacy train_chatbot, chatbot_id={chatbot_id}")
    return retrain_chatbot(chatbot_id)
    
@chatbot_bp.route('/<int:chatbot_id>/train', methods=['POST'])
def retrain_chatbot(chatbot_id):
    """Train a chatbot with stored knowledge base data."""
    current_app.logger.info(f"Entered retrain_chatbot with chatbot_id={chatbot_id}")
    
    try:
        # Get token from cookies first, then header
        token = request.cookies.get('access_token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            current_app.logger.warning("No authentication token provided")
            return jsonify({
                "status": "error",
                "message": "Authentication required"
            }), 200  # Return 200 to prevent redirect issues
            
        payload = verify_jwt(token)
        if not payload:
            current_app.logger.warning("Invalid or expired token")
            return jsonify({
                "status": "error",
                "message": "Invalid or expired token"
            }), 200  # Return 200 to prevent redirect issues
            
        # Get the chatbot
        chatbot = ChatbotConfig.query.get(chatbot_id)
        if not chatbot:
            current_app.logger.warning(f"Chatbot with id={chatbot_id} not found")
            return jsonify({
                "status": "error",
                "message": "Chatbot not found"
            }), 404
        
        # Check if knowledge base exists
        if not chatbot.knowledge_base or not isinstance(chatbot.knowledge_base, dict):
            current_app.logger.warning(f"Chatbot {chatbot_id} has no knowledge base")
            return jsonify({
                "status": "error",
                "message": "Chatbot has no knowledge base to train on"
            }), 400
        
        # Check if FAQs exist in knowledge base
        faqs = chatbot.knowledge_base.get('faqs', [])
        if not faqs or not isinstance(faqs, list) or len(faqs) == 0:
            current_app.logger.warning(f"Chatbot {chatbot_id} has no FAQs in knowledge base")
            return jsonify({
                "status": "error",
                "message": "No FAQs found in knowledge base. Please add FAQs first."
            }), 400
            
        # Get configuration settings
        configuration = chatbot.configuration or {}
        
        # Train the model
        try:
            from .model_training import train_model
            pickled_model = train_model(chatbot.knowledge_base, configuration)
            
            # Save the trained model
            chatbot.trained_model = pickled_model
            chatbot.last_trained_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Training completed for chatbot {chatbot_id}")
            return jsonify({
                "status": "success",
                "message": "Chatbot trained successfully",
                "chatbot_id": chatbot.id,
                "last_trained_at": chatbot.last_trained_at.isoformat()
            }), 200
        except Exception as train_error:
            db.session.rollback()
            current_app.logger.error(f"Error during training: {train_error}")
            return jsonify({
                "status": "error", 
                "message": f"Training failed: {str(train_error)}"
            }), 500
    
    except Exception as e:
        current_app.logger.error(f"Unexpected error in retrain_chatbot: {e}")
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500

@chatbot_bp.route('/create', methods=['POST'])
def create_chatbot():
    try:
        # Get user from cookie or token
        token = request.cookies.get('access_token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'Authentication required',
                'data': None
            }), 401
            
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'status': 'error',
                'message': 'Invalid token',
                'data': None
            }), 401
        
        # Get the user from the database
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'data': None
            }), 404
        
        data = request.get_json()
        current_app.logger.info(f"Received data for chatbot creation: {data}")
        
        # Validate required fields
        required_fields = ['bot_name', 'description', 'welcome_message', 'purpose', 'goal', 'role']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Check if chatbot already exists for this company
        company_id = user.company_id or user.id
        current_app.logger.info(f"Looking for existing chatbot for company_id={company_id}")
        existing_chatbot = ChatbotConfig.query.filter_by(company_id=company_id).first()
        
        if existing_chatbot:
            current_app.logger.info(f"Found existing chatbot (id={existing_chatbot.id}), updating it")
            current_app.logger.info(f"Current version before update: {existing_chatbot.version}, type: {type(existing_chatbot.version)}")
            
            # Update the existing chatbot instead of creating a new one
            existing_chatbot.bot_name = data['bot_name']
            existing_chatbot.purpose = data.get('purpose', '')
            existing_chatbot.goal = data.get('goal', '')
            existing_chatbot.role = data.get('role', '')
            
            # Store description and welcome message in configuration
            if not existing_chatbot.configuration:
                existing_chatbot.configuration = {}
            
            existing_chatbot.configuration['description'] = data.get('description', '')
            existing_chatbot.configuration['welcome_message'] = data.get('welcome_message', '')
            
            # Update knowledge base if provided
            if 'knowledge_base' in data and isinstance(data['knowledge_base'], dict):
                existing_chatbot.knowledge_base = data['knowledge_base']
            
            # Make sure version is an integer before incrementing
            if existing_chatbot.version is None:
                current_app.logger.info("Version is None, setting to 1")
                existing_chatbot.version = 1
            elif not isinstance(existing_chatbot.version, int):
                current_app.logger.info(f"Converting version from {type(existing_chatbot.version)} to int")
                try:
                    existing_chatbot.version = int(existing_chatbot.version)
                except (ValueError, TypeError) as e:
                    current_app.logger.error(f"Failed to convert version to int: {e}")
                    existing_chatbot.version = 1
            
            # Increment version number safely
            existing_chatbot.version = existing_chatbot.version + 1
            current_app.logger.info(f"New version after increment: {existing_chatbot.version}")
            
            try:
                db.session.commit()
                current_app.logger.info("Successfully updated existing chatbot")
            except Exception as commit_error:
                db.session.rollback()
                current_app.logger.error(f"Database error during commit: {commit_error}")
                return jsonify({
                    'status': 'error',
                    'message': f"Database error: {commit_error}",
                    'data': None
                }), 500
            
            # Prepare the response data
            response_data = {
                'id': existing_chatbot.id,
                'bot_name': existing_chatbot.bot_name,
                'description': existing_chatbot.configuration.get('description', ''),
                'welcome_message': existing_chatbot.configuration.get('welcome_message', ''),
                'purpose': existing_chatbot.purpose,
                'goal': existing_chatbot.goal,
                'role': existing_chatbot.role,
                'company_id': existing_chatbot.company_id,
                'version': existing_chatbot.version
            }
            
            return jsonify({
                'status': 'success',
                'message': 'Chatbot updated successfully',
                'data': response_data
            }), 200
        
        # Create new chatbot with configuration containing description and welcome_message
        current_app.logger.info(f"No existing chatbot found, creating new one for company_id={company_id}")
        configuration = {
            'description': data.get('description', ''),
            'welcome_message': data.get('welcome_message', '')
        }
        
        chatbot = ChatbotConfig(
            bot_name=data['bot_name'],
            purpose=data.get('purpose', ''),
            goal=data.get('goal', ''),
            role=data.get('role', ''),
            company_id=company_id,
            configuration=configuration,
            knowledge_base=data.get('knowledge_base', {}),
            version=1  # Initialize version as integer
        )
        
        current_app.logger.info(f"Created new chatbot object, version={chatbot.version}, type={type(chatbot.version)}")
        
        try:
            db.session.add(chatbot)
            db.session.commit()
            current_app.logger.info(f"Successfully committed new chatbot to database, id={chatbot.id}")
        except Exception as commit_error:
            db.session.rollback()
            current_app.logger.error(f"Database error during commit of new chatbot: {commit_error}")
            return jsonify({
                'status': 'error',
                'message': f"Database error: {commit_error}",
                'data': None
            }), 500
        
        # Prepare the response data
        response_data = {
            'id': chatbot.id,
            'bot_name': chatbot.bot_name,
            'description': configuration.get('description', ''),
            'welcome_message': configuration.get('welcome_message', ''),
            'purpose': chatbot.purpose,
            'goal': chatbot.goal,
            'role': chatbot.role,
            'company_id': chatbot.company_id,
            'version': chatbot.version,
            'knowledge_base': chatbot.knowledge_base or {}
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Chatbot created successfully',
            'data': response_data
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating/updating chatbot: {str(e)}")
        current_app.logger.error(f"Exception type: {type(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': None
        }), 500

@chatbot_bp.route('/update', methods=['POST'])
def update_chatbot():
    try:
        # Get user from cookie or token
        token = request.cookies.get('access_token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'Authentication required',
                'data': None
            }), 401
            
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'status': 'error',
                'message': 'Invalid token',
                'data': None
            }), 401
        
        # Get the user from the database
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'data': None
            }), 404
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['bot_name', 'description', 'welcome_message', 'purpose', 'goal', 'role']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Get company ID from user
        company_id = user.company_id or user.id
        
        # Find the chatbot
        chatbot = ChatbotConfig.query.filter_by(company_id=company_id).first()
        
        if not chatbot:
            return jsonify({
                'status': 'error',
                'message': 'No chatbot found for this company',
                'data': None
            }), 404
            
        # Initialize configuration if it doesn't exist
        if not chatbot.configuration:
            chatbot.configuration = {}
            
        # Update chatbot fields
        chatbot.bot_name = data['bot_name']
        chatbot.purpose = data['purpose']
        chatbot.goal = data['goal']
        chatbot.role = data['role']
        
        # Store description and welcome_message in configuration
        chatbot.configuration['description'] = data['description']
        chatbot.configuration['welcome_message'] = data['welcome_message']
        
        # Update knowledge base if provided
        if 'knowledge_base' in data and isinstance(data['knowledge_base'], dict):
            chatbot.knowledge_base = data['knowledge_base']
        
        # Make sure version is an integer before incrementing
        if chatbot.version is None:
            current_app.logger.info("Version is None, setting to 1")
            chatbot.version = 1
        elif not isinstance(chatbot.version, int):
            current_app.logger.info(f"Converting version from {type(chatbot.version)} to int")
            try:
                chatbot.version = int(chatbot.version)
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"Failed to convert version to int: {e}")
                chatbot.version = 1
        
        # Safely increment version
        chatbot.version = chatbot.version + 1
        current_app.logger.info(f"New version after increment: {chatbot.version}")
        
        # Mark the configuration as modified to ensure SQLAlchemy updates it
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(chatbot, "configuration")
        
        # Set the updated_at timestamp
        chatbot.updated_at = datetime.utcnow()
        
        # Ensure the chatbot is marked as not deleted upon update
        chatbot.is_deleted = False
        
        db.session.commit()
        
        # Get values from configuration for response
        configuration = chatbot.configuration or {}
        
        # Safely handle created_at field
        created_at_str = None
        if hasattr(chatbot, 'created_at') and chatbot.created_at:
            created_at_str = chatbot.created_at.isoformat()
        
        return jsonify({
            'status': 'success',
            'message': 'Chatbot updated successfully',
            'data': {
                'id': chatbot.id,
                'bot_name': chatbot.bot_name,
                'description': configuration.get('description', ''),
                'welcome_message': configuration.get('welcome_message', ''),
                'purpose': chatbot.purpose,
                'goal': chatbot.goal,
                'role': chatbot.role,
                'company_id': chatbot.company_id,
                'version': chatbot.version,
                'created_at': created_at_str,
                'updated_at': datetime.utcnow().isoformat()
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating chatbot: {str(e)}")
        current_app.logger.error(f"Error type: {type(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': None
        }), 500

@chatbot_bp.route('/<int:chatbot_id>/analytics', methods=['GET'])
@require_feature(Feature.ADVANCED_ANALYTICS)
def get_analytics(chatbot_id):
    """Get analytics for a chatbot."""
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    
    # Analytics logic here
    try:
        # Your analytics implementation
        return jsonify({"analytics": {}}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chatbot_bp.route('/<int:chatbot_id>/api-key', methods=['POST'])
@require_feature(Feature.API_ACCESS)
def generate_api_key(chatbot_id):
    """Generate an API key for a chatbot."""
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    
    try:
        # API key generation logic here
        return jsonify({"api_key": "generated-api-key"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chatbot_bp.route('/<int:chatbot_id>/white-label', methods=['POST'])
@require_feature(Feature.WHITE_LABEL)
def configure_white_label(chatbot_id):
    """Configure white-label settings for a chatbot."""
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    
    try:
        # White-label configuration logic here
        return jsonify({"message": "White-label configured successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chatbot_bp.route('/<int:chatbot_id>/custom-model', methods=['POST'])
@require_feature(Feature.CUSTOM_MODELS)
def configure_custom_model(chatbot_id):
    """Configure custom model settings for a chatbot."""
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    
    try:
        # Custom model configuration logic here
        return jsonify({"message": "Custom model configured successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

###############################################
# 4. Admin Chatbot Endpoints
###############################################

@admin_chatbots_bp.route("", methods=["GET"])
def get_admin_chatbot():
    print("DEBUG: Entered get_admin_chatbot with client_id=", request.args.get("client_id"))
    client_id = request.args.get("client_id")
    if not client_id:
        print("DEBUG: client_id is required in get_admin_chatbot")
        return jsonify({"error": "client_id is required"}), 400
    chatbot = ChatbotConfig.query.filter_by(company_id=client_id).first()
    if not chatbot:
        print("DEBUG: No chatbot found for client_id=", client_id)
        return jsonify({}), 200
    data = {
        "company_id": chatbot.company_id,
        "bot_name": chatbot.bot_name,
        "configuration": chatbot.configuration,
        "goal": chatbot.goal,
        "id": chatbot.id,
        "knowledge_base": chatbot.knowledge_base,
        "last_trained_at": chatbot.last_trained_at.isoformat() if chatbot.last_trained_at else None,
        "subscription_plan": chatbot.subscription_plan,
        "purpose": chatbot.purpose,
        "role": chatbot.role,
        "version": chatbot.version
    }
    print("DEBUG: Returning chatbot data for client_id=", client_id)
    return jsonify(data), 200

@admin_chatbots_bp.route("", methods=["POST"])
def create_admin_chatbot():
    print("DEBUG: Entered create_admin_chatbot (POST). Checking content_type.")
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in create_admin_chatbot")
        return jsonify({"error": "Authorization header missing"}), 401
    token = auth_header.split(" ")[-1]
    if not verify_jwt(token):
        print("DEBUG: Invalid or expired token in create_admin_chatbot")
        return jsonify({"error": "Invalid or expired token"}), 401
    content_type = request.content_type or ""
    print("DEBUG: content_type is:", content_type)
    if content_type.startswith("multipart/form-data"):
        print("DEBUG: create_admin_chatbot (multipart branch)")
        form_data = request.form.to_dict()
        company_id = form_data.get("company_id")
        if not company_id:
            print("DEBUG: Missing company_id in create_admin_chatbot (multipart)")
            return jsonify({"error": "company_id is required"}), 400
        existing = ChatbotConfig.query.filter_by(company_id=company_id).first()
        if existing:
            print("DEBUG: Chatbot already exists for company_id=", company_id)
            return jsonify({"error": f"A chatbot already exists for company {company_id}. Only one allowed."}), 400
        bot_name = form_data.get("bot_name")
        purpose = form_data.get("purpose")
        goal = form_data.get("goal")
        role = form_data.get("role")
        payment_plan = form_data.get("payment_plan")  # This will be used as subscription_plan.
        config_str = form_data.get("configuration", "{}")
        kb_str = form_data.get("knowledge_base", "{}")
        try:
            configuration = json.loads(config_str)
        except:
            configuration = {}
        configuration["purpose"] = purpose
        configuration["goal"] = goal
        configuration["role"] = role
        try:
            knowledge_base = json.loads(kb_str)
        except:
            knowledge_base = {}
        kb_file = request.files.get("file")
        if kb_file and kb_file.filename:
            print("DEBUG: File uploaded in create_admin_chatbot (multipart) => Overwriting FAQs.")
            upload_folder = os.path.join("static", "uploads", "training_data")
            os.makedirs(upload_folder, exist_ok=True)
            extension = os.path.splitext(kb_file.filename)[1].lower()
            filename = f"training_{uuid.uuid4().hex}{extension}"
            file_path = os.path.join(upload_folder, filename)
            kb_file.save(file_path)
            faqs = []
            if extension in [".jsonl", ".json"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            obj = json.loads(line)
                            faqs.append(obj)
                        except:
                            pass
                knowledge_base["faqs"] = faqs
            elif extension == ".csv":
                with open(file_path, "r", encoding="utf-8") as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        if len(row) >= 2:
                            faqs.append({"question": row[0], "answer": row[1]})
                knowledge_base["faqs"] = faqs
        new_chatbot = ChatbotConfig(
            company_id=int(company_id),
            chatbot_id=str(company_id),
            bot_name=bot_name,
            purpose=purpose,
            goal=goal,
            role=role,
            subscription_plan=payment_plan,
            configuration=configuration,
            knowledge_base=knowledge_base,
            version=1,
            last_trained_at=datetime.utcnow()
        )
        try:
            db.session.add(new_chatbot)
            db.session.commit()
            print("DEBUG: Created new chatbot in create_admin_chatbot with id=", new_chatbot.id)
            return jsonify({
                "message": "Chatbot created successfully",
                "company_id": new_chatbot.company_id,
                "id": new_chatbot.id,
                "chatbot_id": new_chatbot.chatbot_id,
                "version": new_chatbot.version,
                "knowledge_base": new_chatbot.knowledge_base,
                "subscription_plan": new_chatbot.subscription_plan
            }), 201
        except Exception as e:
            db.session.rollback()
            print("DEBUG: Error creating chatbot (multipart):", e)
            return jsonify({"error": "Error creating chatbot", "details": str(e)}), 500

    elif content_type.startswith("application/json"):
        print("DEBUG: create_admin_chatbot (JSON branch)")
        data = request.get_json()
        if not data:
            print("DEBUG: Missing JSON body in create_admin_chatbot")
            return jsonify({"error": "Missing JSON body"}), 400
        company_id = data.get("company_id")
        if not company_id:
            print("DEBUG: Missing company_id in create_admin_chatbot (JSON)")
            return jsonify({"error": "company_id is required"}), 400
        existing = ChatbotConfig.query.filter_by(company_id=company_id).first()
        if existing:
            print("DEBUG: Chatbot already exists for company_id=", company_id)
            return jsonify({"error": f"A chatbot already exists for company {company_id}. Only one allowed."}), 400
        bot_name = data.get("bot_name")
        purpose = data.get("purpose")
        goal = data.get("goal")
        role = data.get("role")
        payment_plan = data.get("payment_plan", "free_trial")
        configuration = data.get("configuration", {})
        knowledge_base = data.get("knowledge_base", {})
        configuration["purpose"] = purpose
        configuration["goal"] = goal
        configuration["role"] = role
        new_chatbot = ChatbotConfig(
            company_id=int(company_id),
            chatbot_id=str(company_id),
            bot_name=bot_name,
            purpose=purpose,
            goal=goal,
            role=role,
            subscription_plan=payment_plan,
            configuration=configuration,
            knowledge_base=knowledge_base,
            version=1,
            last_trained_at=datetime.utcnow()
        )
        try:
            db.session.add(new_chatbot)
            db.session.commit()
            print("DEBUG: Created new chatbot in create_admin_chatbot with id=", new_chatbot.id)
            return jsonify({
                "message": "Chatbot created successfully",
                "company_id": new_chatbot.company_id,
                "id": new_chatbot.id,
                "chatbot_id": new_chatbot.chatbot_id,
                "version": new_chatbot.version,
                "knowledge_base": new_chatbot.knowledge_base,
                "subscription_plan": new_chatbot.subscription_plan
            }), 201
        except Exception as e:
            db.session.rollback()
            print("DEBUG: Error creating chatbot (JSON):", e)
            return jsonify({"error": "Error creating chatbot", "details": str(e)}), 500
    else:
        print("DEBUG: Unsupported Media Type in create_admin_chatbot")
        return jsonify({"error": "Unsupported Media Type"}), 415

@admin_chatbots_bp.route("/<int:chatbot_id>", methods=["PUT"])
def update_admin_chatbot(chatbot_id):
    print("DEBUG: Entered update_admin_chatbot (PUT), chatbot_id=", chatbot_id)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in update_admin_chatbot")
        return jsonify({"error": "Authorization header missing"}), 401
    token = auth_header.split(" ")[-1]
    if not verify_jwt(token):
        print("DEBUG: Invalid or expired token in update_admin_chatbot")
        return jsonify({"error": "Invalid or expired token"}), 401
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        print("DEBUG: Chatbot not found, id=", chatbot_id)
        return jsonify({"error": "Chatbot not found"}), 404
    content_type = request.content_type or ""
    print("DEBUG: content_type is:", content_type)
    if content_type.startswith("multipart/form-data"):
        print("DEBUG: update_admin_chatbot => MULTIPART branch => Overwriting old FAQs.")
        form_data = request.form.to_dict()
        bot_name = form_data.get("bot_name", chatbot.bot_name)
        purpose = form_data.get("purpose", chatbot.purpose)
        goal = form_data.get("goal", chatbot.goal)
        role = form_data.get("role", chatbot.role)
        payment_plan = form_data.get("payment_plan", chatbot.subscription_plan)
        if not payment_plan or str(payment_plan).strip() == "":
            from users.models import User
            user_obj = User.query.filter((User.company_id == chatbot.company_id) | (User.id == chatbot.company_id)).first()
            payment_plan = user_obj.subscription_plan or "basic"
        config_str = form_data.get("configuration", "{}")
        kb_str = form_data.get("knowledge_base", "{}")
        try:
            new_config = json.loads(config_str)
        except:
            new_config = chatbot.configuration or {}
        new_config["bot_name"] = bot_name
        new_config["purpose"] = purpose
        new_config["goal"] = goal
        new_config["role"] = role
        try:
            new_kb = json.loads(kb_str)
        except:
            new_kb = chatbot.knowledge_base or {}
        kb_file = request.files.get("file")
        if kb_file and kb_file.filename:
            print("DEBUG: File found in update_admin_chatbot => Overwriting .faqs with new file data.")
            upload_folder = os.path.join("static", "uploads", "training_data")
            os.makedirs(upload_folder, exist_ok=True)
            extension = os.path.splitext(kb_file.filename)[1].lower()
            filename = f"training_{uuid.uuid4().hex}{extension}"
            file_path_on_disk = os.path.join(upload_folder, filename)
            kb_file.save(file_path_on_disk)
            faqs = []
            if extension in [".json", ".jsonl"]:
                print("DEBUG: Reading JSON/JSONL to build faqs from scratch")
                with open(file_path_on_disk, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        faqs.append(obj)
                    except:
                        pass
            elif extension == ".csv":
                print("DEBUG: Reading CSV to build faqs from scratch")
                with open(file_path_on_disk, "r", encoding="utf-8") as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        if len(row) >= 2:
                            faqs.append({"question": row[0], "answer": row[1]})
            print(f"DEBUG: Built new faqs list with length={len(faqs)}. Overwriting old knowledge_base.")
            new_kb["faqs"] = faqs
        new_config["bot_name"] = bot_name
        new_config["purpose"] = purpose
        new_config["goal"] = goal
        new_config["role"] = role
        chatbot.bot_name = bot_name
        chatbot.purpose = purpose
        chatbot.goal = goal
        chatbot.role = role
        chatbot.payment_plan = payment_plan  # stored field (used as subscription_plan)
        chatbot.configuration = new_config
        chatbot.knowledge_base = new_kb
        chatbot.version = (chatbot.version or 0) + 1
        chatbot.last_trained_at = datetime.utcnow()
        try:
            db.session.commit()
            print(f"DEBUG: Chatbot updated successfully (id={chatbot_id}). FAQs length=", len(chatbot.knowledge_base.get("faqs", [])))
            return jsonify({
                "message": "Chatbot updated successfully",
                "company_id": chatbot.company_id,
                "id": chatbot.id,
                "chatbot_id": chatbot.chatbot_id,
                "version": chatbot.version,
                "knowledge_base": chatbot.knowledge_base,
                "subscription_plan": chatbot.subscription_plan
            }), 200
        except Exception as e:
            db.session.rollback()
            print("DEBUG: Failed to update chatbot in MULTIPART branch:", e)
            return jsonify({"error": "Failed to update chatbot", "details": str(e)}), 500
    elif content_type.startswith("application/json"):
        print("DEBUG: update_admin_chatbot => JSON body branch => Overwriting if knowledge_base provided.")
        data = request.get_json() or {}
        chatbot.bot_name = data.get("bot_name", chatbot.bot_name)
        chatbot.purpose = data.get("purpose", chatbot.purpose)
        chatbot.goal = data.get("goal", chatbot.goal)
        chatbot.role = data.get("role", chatbot.role)
        payment_plan = data.get("subscription_plan", chatbot.subscription_plan)
        if not payment_plan or str(payment_plan).strip() == "":
            from users.models import User
            user_obj = User.query.filter((User.company_id == chatbot.company_id) | (User.id == chatbot.company_id)).first()
            payment_plan = user_obj.subscription_plan or "basic"
        chatbot.payment_plan = payment_plan
        new_config = data.get("configuration", {})
        new_config["bot_name"] = chatbot.bot_name
        new_config["purpose"] = chatbot.purpose
        new_config["goal"] = chatbot.goal
        new_config["role"] = chatbot.role
        chatbot.configuration = new_config
        if "knowledge_base" in data:
            chatbot.knowledge_base = data["knowledge_base"]
        else:
            chatbot.knowledge_base = {}
        chatbot.version = (chatbot.version or 0) + 1
        chatbot.last_trained_at = datetime.utcnow()
        try:
            db.session.commit()
            print(f"DEBUG: Chatbot updated successfully (id={chatbot_id}). FAQs length=", len(chatbot.knowledge_base.get("faqs", [])))
            return jsonify({
                "message": "Chatbot updated successfully",
                "company_id": chatbot.company_id,
                "id": chatbot.id,
                "chatbot_id": chatbot.chatbot_id,
                "version": chatbot.version,
                "knowledge_base": chatbot.knowledge_base,
                "subscription_plan": chatbot.subscription_plan
            }), 200
        except Exception as e:
            db.session.rollback()
            print("DEBUG: Failed to update chatbot in JSON branch:", e)
            return jsonify({"error": "Failed to update chatbot", "details": str(e)}), 500
    else:
        print("DEBUG: Unsupported Media Type in update_admin_chatbot =>", content_type)
        return jsonify({"error": "Unsupported Media Type"}), 415

@admin_bp.route('/chatbots/<int:chatbot_id>', methods=['DELETE'])
def delete_chatbot(chatbot_id):
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code
    try:
        chatbot = ChatbotConfig.query.get(chatbot_id)
        if not chatbot or chatbot.company_id != company_id:
            return jsonify({"error": "Chatbot not found for your company"}), 404
            
        # Start a transaction
        try:
            # Get all session IDs associated with this chatbot
            session_ids = [session.id for session in ChatSession.query.filter_by(chatbot_id=chatbot_id).all()]
            
            # Delete all messages from those sessions in a single query
            if session_ids:
                current_app.logger.info(f"Admin deleting messages from {len(session_ids)} chat sessions")
                deleted_messages = ChatMessage.query.filter(ChatMessage.session_id.in_(session_ids)).delete(synchronize_session='fetch')
                current_app.logger.info(f"Admin deleted {deleted_messages} chat messages")
            
                # Delete all sessions in a single query
                deleted_sessions = ChatSession.query.filter_by(chatbot_id=chatbot_id).delete(synchronize_session='fetch')
                current_app.logger.info(f"Admin deleted {deleted_sessions} chat sessions")
            
            # Finally delete the chatbot
            db.session.delete(chatbot)
            db.session.commit()
            
            return jsonify({"message": "Chatbot deleted successfully"}), 200
            
        except Exception as inner_exception:
            db.session.rollback()
            raise inner_exception
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/chatbots/<int:chatbot_id>/retrain', methods=['POST'])
def retrain_chatbot_route(chatbot_id):
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot or chatbot.company_id != company_id:
        return jsonify({"error": "Chatbot not found for your company"}), 404
    kb = chatbot.knowledge_base or {}
    conf = chatbot.configuration or {}
    try:
        pickled = train_model(kb, conf)
        print(f"DEBUG: Pickled model size in retrain: {len(pickled)} bytes")
        chatbot.trained_model = pickled
        chatbot.last_trained_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "message": "Retrained successfully",
            "company_id": chatbot.company_id,
            "id": chatbot.id,
            "chatbot_id": chatbot.chatbot_id,
            "version": chatbot.version,
            "last_trained_at": chatbot.last_trained_at.isoformat()
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code
    try:
        chatbots = ChatbotConfig.query.filter_by(company_id=company_id).all()
        data = [chatbot_to_dict(c) for c in chatbots]
        return jsonify({"chatbots": data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chatbot_bp.route('/info', methods=['GET'])
def get_chatbot():
    try:
        # Get token from cookie or Authorization header
        token = request.cookies.get('access_token')
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'Authentication required'
            }), 200  # Using 200 to avoid redirect issues
        
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'status': 'error',
                'message': 'Invalid token'
            }), 200  # Using 200 to avoid redirect issues
        
        # Get the user from the database
        user_id = payload.get('user_id')
        from users.models import User
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 200
        
        # Get company_id (either user's company or user's id for self-employed)
        company_id = user.company_id or user.id
        
        # Get chatbot for the company
        chatbot = ChatbotConfig.query.filter_by(company_id=company_id).first()
        
        if not chatbot:
            return jsonify({
                'status': 'error',
                'message': 'No chatbot found for this company'
            }), 200
        
        # Prepare response data
        configuration = chatbot.configuration or {}
        response_data = {
            'id': chatbot.id,
            'bot_name': chatbot.bot_name,
            'description': configuration.get('description', ''),
            'welcome_message': configuration.get('welcome_message', ''),
            'purpose': chatbot.purpose,
            'goal': chatbot.goal,
            'role': chatbot.role,
            'company_id': chatbot.company_id,
            'version': chatbot.version,
            'knowledge_base': chatbot.knowledge_base or {}
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Chatbot retrieved successfully',
            'data': response_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving chatbot: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error retrieving chatbot: {str(e)}'
        }), 200  # Using 200 to avoid redirect issues

@chatbot_bp.route('/activities', methods=['GET'])
@login_required
def get_recent_activities():
    """
    Get recent activities for all chatbots associated with the company
    """
    try:
        company_id = current_user.company_id
        limit = request.args.get('limit', 10, type=int)
        
        # Get the company's chatbots
        chatbots = ChatbotConfig.query.filter_by(company_id=company_id).all()
        
        if not chatbots:
            return jsonify({
                'success': True,
                'activities': []
            })
        
        chatbot_ids = [chatbot.id for chatbot in chatbots]
        
        # Get recent message activities
        recent_messages = db.session.query(
            ChatSession.id.label('session_id'),
            ChatMessage.id.label('message_id'),
            ChatMessage.message.label('content'),
            ChatMessage.timestamp.label('created_at'),
            ChatMessage.sender,
            ChatMessage.rating,
            ChatbotConfig.bot_name.label('chatbot_name'),
            ChatbotConfig.id.label('chatbot_id')
        ).join(
            ChatSession,
            ChatMessage.session_id == ChatSession.id
        ).join(
            ChatbotConfig,
            ChatSession.chatbot_id == ChatbotConfig.id
        ).filter(
            ChatbotConfig.id.in_(chatbot_ids)
        ).order_by(
            ChatMessage.timestamp.desc()
        ).limit(limit).all()
        
        # Format activities
        activities = []
        for msg in recent_messages:
            activity_type = 'chat'
            title = f"New message in {msg.chatbot_name}"
            description = f"{'Bot response' if msg.sender == 'bot' else 'User message'}: {msg.content[:50]}..." if len(msg.content or '') > 50 else msg.content
            
            # If the message has a rating, change the type to feedback
            if msg.rating is not None:
                activity_type = 'feedback'
                title = f"Feedback received for {msg.chatbot_name}"
                description = f"User rated a response {msg.rating}/5"
                
            activities.append({
                'type': activity_type,
                'title': title,
                'description': description,
                'timestamp': msg.created_at.isoformat() if msg.created_at else None,
                'chatbot_id': msg.chatbot_id,
                'session_id': msg.session_id,
                'message_id': msg.message_id
            })
        
        # Since we don't have TrainingLog and StatusChangeLog tables yet, 
        # we'll just use message activities for now
        
        # Sort all activities by timestamp
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Limit to the requested number
        activities = activities[:limit]
        
        return jsonify({
            'success': True,
            'activities': activities
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving recent activities: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve recent activities'
        }), 500

@chatbot_bp.route('/upload', methods=['POST'])
def upload_knowledge_base():
    try:
        # Get user from cookie or token
        token = request.cookies.get('access_token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'Authentication required',
                'data': None
            }), 401
            
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'status': 'error',
                'message': 'Invalid token',
                'data': None
            }), 401
        
        # Get the user from the database
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'data': None
            }), 404
            
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No file part in the request',
                'data': None
            }), 400
            
        file = request.files['file']
        
        # Check if filename is empty
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No file selected',
                'data': None
            }), 400
            
        # Check file extension
        allowed_extensions = ['.txt', '.csv', '.json', '.jsonl']
        ext = os.path.splitext(file.filename)[1].lower()
        
        if ext not in allowed_extensions:
            return jsonify({
                'status': 'error',
                'message': f'File type not allowed. Supported formats: {", ".join(allowed_extensions)}',
                'data': None
            }), 400
            
        # Generate a unique filename
        filename = f"{user.company_id or user.id}_{uuid.uuid4().hex}{ext}"
        
        # Make sure the upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Save the file with absolute path
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            file.save(file_path)
            current_app.logger.info(f"File saved to: {file_path}")
        except Exception as e:
            current_app.logger.error(f"Error saving file: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Error saving file: {str(e)}',
                'data': None
            }), 500
            
        # Process the file based on its type
        faqs = []
        
        try:
            if ext in ['.json', '.jsonl']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        faqs.append(obj)
                    except json.JSONDecodeError as e:
                        current_app.logger.error(f"JSON parsing error: {str(e)}")
                        
            elif ext == '.csv':
                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        if len(row) >= 2:
                            faqs.append({"question": row[0], "answer": row[1]})
                            
            elif ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Simple parsing of Q&A format
                qa_pairs = content.split('\n\n')
                for pair in qa_pairs:
                    lines = pair.strip().split('\n')
                    if len(lines) >= 2:
                        q = lines[0].strip()
                        a = '\n'.join(lines[1:]).strip()
                        if q and a:
                            if q.startswith('Q:'):
                                q = q[2:].strip()
                            if a.startswith('A:'):
                                a = a[2:].strip()
                            faqs.append({"question": q, "answer": a})
        
        except Exception as e:
            current_app.logger.error(f"Error processing file: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Error processing file: {str(e)}',
                'data': None
            }), 500
            
        return jsonify({
            'status': 'success',
            'message': 'File uploaded and processed successfully',
            'data': {
                'filename': filename,
                'file_path': file_path,
                'faqs_count': len(faqs),
                'faqs': faqs
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Unexpected error in upload_knowledge_base: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'An unexpected error occurred: {str(e)}',
            'data': None
        }), 500

@chatbot_bp.route('/rate', methods=['POST'])
def rate_message():
    current_app.logger.info("Entered rate_message")
    try:
        # Get data and handle API key or JWT authentication
        data = request.get_json() or {}
        api_key = data.get("apiKey") or request.args.get("apiKey")
        payload = None
        if api_key:
            from admin.models import ApiKey
            api_key_obj = ApiKey.query.filter_by(key=api_key, status='active').first()
            if not api_key_obj:
                current_app.logger.warning("Invalid API key provided for feedback")
                return jsonify({"status": "error", "message": "Invalid API key"}), 200
            # Build a minimal payload for API key auth
            payload = {"company_id": api_key_obj.company_id}
        else:
            # Get token from cookies first, then header
            token = request.cookies.get("access_token")
            if not token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
            if not token:
                current_app.logger.warning("No authentication token provided")
                return jsonify({"status": "error", "message": "Authentication required"}), 200
            payload = verify_jwt(token)
            if not payload:
                current_app.logger.warning("Invalid or expired token")
                return jsonify({"status": "error", "message": "Invalid or expired token"}), 200

        # Extract feedback details
        message_id = data.get("message_id")
        session_id = data.get("session_id")
        rating = data.get("rating")
        feedback = data.get("feedback")
        
        if not rating or (not message_id and not session_id):
            current_app.logger.warning("Missing required fields for rating")
            return jsonify({
                "status": "error",
                "message": "Required fields: rating and either message_id or session_id"
            }), 400

        # Find the message to rate
        message = None
        if message_id:
            message = ChatMessage.query.get(message_id)
        elif session_id:
            # Get the latest bot message in the session
            message = ChatMessage.query.filter_by(
                session_id=session_id,
                sender="bot"
            ).order_by(ChatMessage.timestamp.desc()).first()
        
        if not message:
            current_app.logger.warning(f"No message found with id={message_id} or in session={session_id}")
            return jsonify({
                "status": "error",
                "message": "Message not found"
            }), 404

        # Update the message rating and feedback
        message.rating = rating
        
        # Set feedback based on rating if not provided
        if not feedback:
            if rating >= 4:
                feedback = 'positive'
            elif rating <= 2:
                feedback = 'negative'
            else:
                feedback = 'neutral'
        
        message.feedback = feedback
        current_app.logger.info(f"Setting message {message.id} rating={rating} feedback={feedback}")
        
        # Update the chatbot's satisfaction statistics
        try:
            session = ChatSession.query.get(message.session_id)
            if session and session.chatbot_id:
                chatbot = ChatbotConfig.query.get(session.chatbot_id)
                if chatbot:
                    # Increment total feedback count
                    chatbot.total_feedback_count = (chatbot.total_feedback_count or 0) + 1
                    
                    # If it's positive feedback (rating >= 4 or feedback == 'positive')
                    is_positive = feedback == 'positive'
                    if is_positive:
                        chatbot.positive_feedback_count = (chatbot.positive_feedback_count or 0) + 1
                    
                    # Calculate new satisfaction rate
                    if chatbot.total_feedback_count > 0:
                        chatbot.satisfaction_rate = (chatbot.positive_feedback_count / chatbot.total_feedback_count) * 100
                        
                    current_app.logger.info(f"Updated chatbot {chatbot.id} stats: total={chatbot.total_feedback_count}, "
                                          f"positive={chatbot.positive_feedback_count}, rate={chatbot.satisfaction_rate}%")
        except Exception as e:
            current_app.logger.error(f"Error updating chatbot statistics: {e}")
            # Continue even if statistics update fails
        
        try:
            db.session.commit()
            current_app.logger.info(f"Rating saved for message {message.id}: {rating}")
            return jsonify({
                "status": "success",
                "message": "Rating saved successfully",
                "message_id": message.id
            }), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving rating: {e}")
            return jsonify({
                "status": "error",
                "message": f"Failed to save rating: {e}"
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Unexpected error in rate_message: {e}")
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {e}"
        }), 500

@chatbot_bp.route('/<int:chatbot_id>', methods=['DELETE'])
def delete_chatbot_route(chatbot_id):
    """
    Delete a chatbot for the current company
    This uses the chatbot_bp blueprint which has a different authentication pattern
    """
    try:
        # Get token from cookie or Authorization header
        token = request.cookies.get('access_token')
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'Authentication required'
            }), 401
        
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'status': 'error',
                'message': 'Invalid token'
            }), 401
        
        # Get the user from the database
        user_id = payload.get('user_id')
        from users.models import User
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        # Get company_id (either user's company or user's id for self-employed)
        company_id = user.company_id or user.id
        
        # Find the chatbot to delete
        chatbot = ChatbotConfig.query.filter_by(id=chatbot_id, company_id=company_id).first()
        if not chatbot:
            return jsonify({
                'status': 'error',
                'message': 'Chatbot not found or not owned by your company'
            }), 404
        
        # Start a transaction
        try:
            # Get all session IDs associated with this chatbot
            session_ids = [session.id for session in ChatSession.query.filter_by(chatbot_id=chatbot_id).all()]
            
            # Delete all messages from those sessions in a single query
            if session_ids:
                current_app.logger.info(f"Deleting messages from {len(session_ids)} chat sessions")
                deleted_messages = ChatMessage.query.filter(ChatMessage.session_id.in_(session_ids)).delete(synchronize_session='fetch')
                current_app.logger.info(f"Deleted {deleted_messages} chat messages")
            
                # Delete all sessions in a single query
                deleted_sessions = ChatSession.query.filter_by(chatbot_id=chatbot_id).delete(synchronize_session='fetch')
                current_app.logger.info(f"Deleted {deleted_sessions} chat sessions")
            
            # Finally delete the chatbot
            db.session.delete(chatbot)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Chatbot deleted successfully'
            }), 200
        except Exception as inner_exception:
            db.session.rollback()
            raise inner_exception
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting chatbot: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error deleting chatbot: {str(e)}'
        }), 500

@chatbot_bp.route('/company/api-key', methods=['GET'])
def get_company_api_key():
    current_app.logger.info("Entered get_company_api_key")
    
    # Check authentication - get token from request
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Check for both access_token and permanent_token cookies
        token = request.cookies.get("access_token") or request.cookies.get("permanent_token")
    
    if not token:
        current_app.logger.warning("No authentication token found in get_company_api_key")
        return jsonify({
            'success': False,
            'error': 'Authentication required',
            'response': 'You must be logged in to access this resource.'
        }), 401
    
    # Verify the token and get user data
    user_data = verify_jwt(token)
    if not user_data:
        current_app.logger.warning("Authentication failed in get_company_api_key")
        return jsonify({
            'success': False,
            'error': 'Authentication required',
            'response': 'You must be logged in to access this resource.'
        }), 401
    
    # Get company ID from user data
    company_id = user_data.get('company_id')
    if not company_id:
        current_app.logger.warning("No company_id found in user data")
        return jsonify({
            'success': False,
            'error': 'No company ID associated with user',
            'response': 'Your account is not associated with a company.'
        }), 400
    
    try:
        # Import ApiKey here to avoid circular imports
        from admin.models import ApiKey
        
        # Query the database for an active API key for this company
        # Use status field instead of active field
        api_key = db.session.query(ApiKey).filter_by(
            company_id=company_id,
            status='active'
        ).order_by(
            ApiKey.created_at.desc()  # Get the most recent key
        ).first()
        
        if api_key:
            current_app.logger.info(f"API key found for company_id={company_id}")
            return jsonify({
                'success': True,
                'api_key': api_key.key
            })
        else:
            current_app.logger.warning(f"No active API key found for company_id={company_id}")
            return jsonify({
                'success': False,
                'error': 'No active API key found',
                'response': 'No active API key found for your company. Please contact support to get one.'
            })
    except Exception as e:
        current_app.logger.error(f"Error in get_company_api_key: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Error fetching API key: {str(e)}",
            'response': 'An error occurred while fetching your API key.'
        }), 500

###############################################
# Moving Company Specific Endpoints
###############################################

@chatbot_bp.route('/estimate-moving-cost', methods=['POST'])
def estimate_moving_cost():
    """
    Endpoint for chatbot to estimate moving costs.
    This is used by the chatbot's direct API integration.
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "error": "No data provided"
        }), 400
    
    # Check for required fields
    required_fields = ['company_id', 'origin', 'destination', 'move_size']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "success": False,
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400
    
    company_id = data.get('company_id')
    
    # Get company
    company = Company.query.get(company_id)
    if not company:
        return jsonify({
            "success": False,
            "error": "Company not found"
        }), 404
    
    # Get parameters
    params = MovingParameters.query.filter_by(company_id=company_id).first()
    if not params:
        params = MovingParameters(company_id=company_id)
    
    # Extract data
    origin = data.get('origin', '')
    destination = data.get('destination', '')
    move_size = data.get('move_size', '')
    
    # Get additional options
    has_packing = data.get('packing', False)
    has_storage = data.get('storage', False)
    is_rural = data.get('is_rural', False)
    is_peak_season = data.get('is_peak_season', False)
    
    # Calculate or estimate distance (in a real app, this would use a mapping API)
    # Here using a simplified approach - you could integrate with Google Maps API for actual distances
    distance = data.get('distance')
    if not distance:
        # Simple mock distance calculation (replace with actual API)
        # This is a very simplified placeholder calculation
        import random
        distance = random.randint(30, 500)  # Mock distance between 30 and 500 miles
    
    # Validate move size
    if move_size not in params.move_size_rates:
        return jsonify({
            "success": False,
            "error": f"Invalid move size: {move_size}. Valid options are: {', '.join(params.move_size_rates.keys())}"
        }), 400
    
    try:
        # Calculate base cost
        base_cost = params.move_size_rates[move_size]
        
        # Add distance cost
        distance_cost = distance * params.base_rate_per_mile
        
        # Add packing cost if needed
        packing_cost = 0
        if has_packing:
            packing_cost = params.additional_service_costs['packing'][move_size]
        
        # Add storage cost if needed
        storage_cost = 0
        if has_storage:
            storage_cost = params.additional_service_costs['storage'][move_size]
        
        # Calculate total cost
        total_cost = base_cost + distance_cost + packing_cost + storage_cost
        
        # Apply adjustments
        if is_rural:
            rural_adjustment = total_cost * params.rate_adjustments['rural_location_rate']
            total_cost += rural_adjustment
        
        if is_peak_season:
            seasonal_adjustment = total_cost * params.rate_adjustments['seasonality_rate']
            total_cost += seasonal_adjustment
        
        # Calculate min and max cost range
        min_cost = total_cost
        max_cost = total_cost * params.rate_adjustments['max_cost_multiplier']
        
        # Round costs to 2 decimal places
        min_cost = round(min_cost, 2)
        max_cost = round(max_cost, 2)
        
        # Create detailed breakdown for response
        cost_breakdown = {
            "base_cost": round(base_cost, 2),
            "distance_cost": round(distance_cost, 2),
            "distance_miles": distance,
            "packing_cost": round(packing_cost, 2) if has_packing else 0,
            "storage_cost": round(storage_cost, 2) if has_storage else 0,
            "rural_location_adjustment": round(rural_adjustment, 2) if is_rural else 0,
            "seasonal_adjustment": round(seasonal_adjustment, 2) if is_peak_season else 0,
            "subtotal": round(total_cost, 2),
            "min_cost": min_cost,
            "max_cost": max_cost,
            "currency": "USD"
        }
        
        # Generate a human-readable explanation
        explanation = (
            f"Based on moving a {move_size} from {origin} to {destination} "
            f"(approx. {distance} miles), the estimated cost is between ${min_cost} and ${max_cost}.\n\n"
            f"This includes a base cost of ${base_cost} for a {move_size} and ${distance_cost} for the distance."
        )
        
        if has_packing:
            explanation += f"\nPacking services add ${packing_cost}."
        
        if has_storage:
            explanation += f"\nStorage services add ${storage_cost}."
        
        if is_rural:
            explanation += f"\nA rural location adjustment of ${rural_adjustment} is applied."
        
        if is_peak_season:
            explanation += f"\nA peak season adjustment of ${seasonal_adjustment} is applied."
        
        # Record this estimate for analytics (optional)
        # log_estimate_request(company_id, origin, destination, move_size, cost_breakdown)
        
        return jsonify({
            "success": True,
            "estimate": {
                "min_cost": min_cost,
                "max_cost": max_cost,
                "currency": "USD",
                "breakdown": cost_breakdown,
                "explanation": explanation,
                "origin": origin,
                "destination": destination,
                "move_size": move_size,
                "distance": distance
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error calculating cost estimate: {str(e)}"
        }), 500

@chatbot_bp.route('/register-complaint', methods=['POST'])
def register_complaint():
    """
    Endpoint for chatbot to register a customer complaint
    This automatically creates a support ticket from the chatbot
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "error": "No data provided"
        }), 400
    
    # Check for required fields
    required_fields = ['company_id', 'name', 'email', 'subject', 'details']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "success": False,
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400
    
    company_id = data.get('company_id')
    name = data.get('name')
    email = data.get('email')
    subject = data.get('subject')
    details = data.get('details')
    topic = data.get('topic', 'complaint')  # Default topic is complaint
    
    # Get company
    company = Company.query.get(company_id)
    if not company:
        return jsonify({
            "success": False,
            "error": "Company not found"
        }), 404
    
    try:
        # Check if user exists or create a new one
        user = User.query.filter_by(user_email=email).first()
        if not user:
            # Create a new user for this complaint
            user = User(
                user_email=email,
                user_name=name,
                company_id=company_id,
                company_name=company.name,
                is_verified=False
            )
            # Set a random password (user won't log in directly)
            import secrets
            user.set_password(secrets.token_urlsafe(12))
            db.session.add(user)
            db.session.commit()
        
        # Create a support ticket
        from admin_panel.models import SupportTicket
        import uuid
        
        new_ticket = SupportTicket(
            user_id=user.id,
            company_id=company_id,
            subject=subject,
            topic=topic,
            details=details,
            status='open',
            ticket_number=f"COMP-{uuid.uuid4().hex[:8].upper()}"
        )
        
        db.session.add(new_ticket)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Complaint registered successfully",
            "ticket_id": new_ticket.id,
            "ticket_number": new_ticket.ticket_number
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Error registering complaint: {str(e)}"
        }), 500

@chatbot_bp.route('/jsonp/session/<int:session_id>/add_message', methods=['GET'])
@jsonp
def jsonp_add_chat_message(session_id):
    """JSONP endpoint for adding chat messages via GET for embed script (auth bypass)."""
    print(f"DEBUG: Entered jsonp_add_chat_message bypass, session_id={session_id}")
    # Bypass authentication: trust sessionId
    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print(f"DEBUG: Session not found in JSONP add message, id={session_id}")
        resp = jsonify({"status": "error", "message": "Chat session not found"})
        resp.status_code = 404
        return resp
    # Get sender and message
    sender = request.args.get('sender')
    message_text = request.args.get('message')
    if not sender or not message_text:
        print("DEBUG: Missing sender or message in JSONP add message")
        resp = jsonify({"status": "error", "message": "sender and message are required"})
        resp.status_code = 400
        return resp
    if sender not in ["user", "bot", "assistant"]:
        print(f"DEBUG: Invalid sender '{sender}' in JSONP add message")
        resp = jsonify({"status": "error", "message": "Invalid sender; must be 'user' or 'bot'"})
        resp.status_code = 400
        return resp
    # Create and store message
    new_msg = ChatMessage(session_id=session_id, sender=sender, message=message_text)
    try:
        db.session.add(new_msg)
        db.session.commit()
        print(f"DEBUG: Added new message with id={new_msg.id} via JSONP")
        return jsonify({"status": "success", "message_id": new_msg.id, "timestamp": new_msg.timestamp.isoformat()})
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Failed to add message via JSONP: {e}")
        resp = jsonify({"status": "error", "message": f"Failed to add message: {e}"})
        resp.status_code = 500
        return resp
