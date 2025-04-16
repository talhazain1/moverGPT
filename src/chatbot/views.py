# chatbot/views.py

import os
import json
import csv
import uuid
import openai
from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy.orm.attributes import flag_modified

from core.database import db
from core.utils import verify_jwt
from users.models import User
from chatbot.models import ChatbotConfig, ChatSession, ChatMessage
from chatbot.model_training import train_model
from chatbot.model_inference import run_inference_openai
from subscriptions.decorators import require_feature
from subscriptions.features import Features

# Define blueprints.
chatbot_bp = Blueprint('chatbot', __name__)
admin_chatbots_bp = Blueprint("admin_chatbots", __name__)
admin_bp = Blueprint("admin", __name__)

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

@chatbot_bp.route('/session', methods=['POST'])
def create_chat_session():
    print("DEBUG: Entered create_chat_session")
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header")
        return jsonify({"error": "Authorization header missing"}), 401

    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token")
        return jsonify({"error": "Invalid or expired token"}), 401

    user_id = payload.get("user_id")
    if not user_id:
        print("DEBUG: No user_id in token")
        return jsonify({"error": "No user_id found in token"}), 400

    session_obj = ChatSession(user_id=user_id)
    try:
        db.session.add(session_obj)
        db.session.commit()
        print("DEBUG: Created ChatSession with id=", session_obj.id)
        return jsonify({
            "session_id": session_obj.id,
            "created_at": session_obj.created_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to create session:", e)
        return jsonify({"error": f"Failed to create session: {e}"}), 500

@chatbot_bp.route('/session/<int:session_id>/message', methods=['POST'])
def add_chat_message(session_id):
    print("DEBUG: Entered add_chat_message, session_id=", session_id)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in add_chat_message")
        return jsonify({"error": "Authorization header missing"}), 401

    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in add_chat_message")
        return jsonify({"error": "Invalid or expired token"}), 401

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
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in get_chat_messages")
        return jsonify({"error": "Invalid or expired token"}), 401

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
    return jsonify({"session_id": session_id, "messages": msg_list}), 200

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

###############################################
# 2. Inference with Auto-Training and Message Storage
###############################################

@chatbot_bp.route('/inference', methods=['POST'])
def chatbot_inference():
    print("DEBUG: Entered chatbot_inference")
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in chatbot_inference")
        return jsonify({"error": "Authorization header missing"}), 401
    token = auth_header.split(" ")[-1]
    if not verify_jwt(token):
        print("DEBUG: Invalid or expired token in chatbot_inference")
        return jsonify({"error": "Invalid or expired token"}), 401
    data = request.get_json() or {}
    company_id = data.get("company_id")
    query = data.get("query")
    session_id = data.get("session_id")
    history = data.get("history", [])
    if not company_id or not query:
        print("DEBUG: Missing company_id or query in chatbot_inference")
        return jsonify({"error": "company_id and query are required"}), 400

    chatbot_config = ChatbotConfig.query.filter_by(company_id=company_id).first()
    if not chatbot_config:
        print(f"DEBUG: No chatbot found for company_id={company_id}")
        return jsonify({"error": f"No chatbot found for company_id={company_id}"}), 404

    # If no trained model is present, auto-train the chatbot.
    if not chatbot_config.trained_model:
        print("DEBUG: No trained_model found on chatbot_config. Automatically training now.")
        try:
            pickled_model = train_model(chatbot_config.knowledge_base or {}, chatbot_config.configuration or {})
            print(f"DEBUG: Pickled model size (auto-trained): {len(pickled_model)} bytes")
            chatbot_config.trained_model = pickled_model
            chatbot_config.last_trained_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            print("DEBUG: Automatic training failed:", e)
            # If auto-training fails, return the fallback message.
            return jsonify({"response": "I'm not trained yet. Please train me on a knowledge base.", "session_id": session_id}), 200

    if not session_id:
        print("DEBUG: No session_id provided. Creating new session.")
        new_session = ChatSession(user_id=verify_jwt(token).get("user_id"), chatbot_id=chatbot_config.id)
        try:
            db.session.add(new_session)
            db.session.commit()
            session_id = new_session.id
            print("DEBUG: Created new session with id=", session_id)
        except Exception as e:
            db.session.rollback()
            print("DEBUG: Failed to create new session in inference:", e)
            return jsonify({"error": f"Failed to create new session: {e}"}), 500

    # Store the user's query as a message.
    user_message = ChatMessage(session_id=session_id, sender="user", message=query)
    try:
        db.session.add(user_message)
        db.session.commit()
        print("DEBUG: Stored user query message, id=", user_message.id)
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to store user message:", e)
    try:
        answer = run_inference_openai(chatbot_config, query, history=history, top_n=3)
    except Exception as e:
        print("DEBUG: Inference error:", e)
        return jsonify({"error": f"Inference error: {e}"}), 500
    bot_message = ChatMessage(session_id=session_id, sender="bot", message=answer)
    try:
        db.session.add(bot_message)
        db.session.commit()
        print("DEBUG: Stored bot answer message, id=", bot_message.id)
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to store bot message:", e)
    print("DEBUG: chatbot_inference returning answer")
    return jsonify({"response": answer, "session_id": session_id}), 200

###############################################
# 3. Train / Retrain Endpoint
###############################################

@chatbot_bp.route('/train/<int:chatbot_id>', methods=['POST'])
def train_chatbot(chatbot_id):
    print("DEBUG: Entered train_chatbot, chatbot_id=", chatbot_id)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Missing Authorization header in train_chatbot")
        return jsonify({"error": "Authorization header missing"}), 401
    token = auth_header.split(" ")[-1]
    if not verify_jwt(token):
        print("DEBUG: Invalid or expired token in train_chatbot")
        return jsonify({"error": "Invalid or expired token"}), 401
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        print("DEBUG: Chatbot not found for id=", chatbot_id)
        return jsonify({"error": "Chatbot not found"}), 404
    try:
        pickled_model = train_model(chatbot.knowledge_base or {}, chatbot.configuration or {})
        print(f"DEBUG: Pickled model size: {len(pickled_model)} bytes")
        chatbot.trained_model = pickled_model
        chatbot.last_trained_at = datetime.utcnow()
        db.session.commit()
        print("DEBUG: Training complete for chatbot_id=", chatbot_id)
        return jsonify({
            "message": "Training complete",
            "chatbot_id": chatbot.id,
            "company_id": chatbot.company_id,
            "last_trained_at": chatbot.last_trained_at.isoformat()
        }), 200
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Training failed:", e)
        return jsonify({"error": f"Training failed: {e}"}), 500
    
@chatbot_bp.route('/<int:chatbot_id>/train', methods=['POST'])
@require_feature(Features.ADVANCED_CHATBOT)
def retrain_chatbot(chatbot_id):
    """Train a chatbot with new data."""
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    
    # Training logic here
    try:
        # Your training implementation
        return jsonify({"message": "Chatbot trained successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chatbot_bp.route('/create', methods=['POST'])
@require_feature(Features.BASIC_CHATBOT)
def create_chatbot():
    """Create a new chatbot."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    
    # Get user from token
    token = request.headers.get("Authorization", "").split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401
    
    user_id = payload.get("user_id")
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Check if user has reached chatbot limit based on their plan
    if user.subscription_plan == "basic":
        existing_chatbots = ChatbotConfig.query.filter_by(user_id=user_id).count()
        if existing_chatbots >= 1:  # Basic plan allows only 1 chatbot
            return jsonify({"error": "Basic plan allows only 1 chatbot. Please upgrade to create more."}), 403
    
    # Create chatbot
    chatbot = ChatbotConfig(
        user_id=user_id,
        name=data.get("name"),
        description=data.get("description"),
        configuration=data.get("configuration", {})
    )
    
    try:
        db.session.add(chatbot)
        db.session.commit()
        return jsonify({"message": "Chatbot created successfully", "chatbot_id": chatbot.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@chatbot_bp.route('/<int:chatbot_id>/update', methods=['PUT'])
@require_feature(Features.BASIC_CHATBOT)
def update_chatbot(chatbot_id):
    """Update an existing chatbot."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    
    # Update chatbot fields
    if "name" in data:
        chatbot.name = data["name"]
    if "description" in data:
        chatbot.description = data["description"]
    if "configuration" in data:
        chatbot.configuration = data["configuration"]
    
    try:
        db.session.commit()
        return jsonify({"message": "Chatbot updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@chatbot_bp.route('/<int:chatbot_id>/analytics', methods=['GET'])
@require_feature(Features.ADVANCED_ANALYTICS)
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
@require_feature(Features.API_ACCESS)
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
@require_feature(Features.WHITE_LABEL)
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
@require_feature(Features.CUSTOM_MODELS)
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

@admin_bp.route("/<int:chatbot_id>", methods=["PUT"])
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
    print("DEBUG: content_type in update_admin_chatbot is:", content_type)
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
                import csv
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
        chatbot.version = (chatbot.version or 1) + 1
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
        chatbot.version = (chatbot.version or 1) + 1
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
        db.session.delete(chatbot)
        db.session.commit()
        return jsonify({"message": "Chatbot deleted successfully"}), 200
    except Exception as e:
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
