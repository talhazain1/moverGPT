"""
admin_panel/views.py

This module provides admin endpoints for managing chatbots.
All references to a chatbot's plan now use the unified field 'subscription_plan'.
"""

import os
import uuid
import json
import csv
from datetime import datetime
from flask import Blueprint, request, jsonify
from core.utils import verify_jwt
from core.database import db
from users.models import User
from chatbot.models import ChatbotConfig
from chatbot.model_training import train_model

admin_bp = Blueprint('admin', __name__)

def get_logged_in_company_id():
    """
    Extracts the company_id from the JWT.
    Checks first the Authorization header and then falls back to the "access_token" cookie.
    Returns a tuple (company_id, error_response, status_code).
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

    user_id = payload.get("user_id")
    user = User.query.get(user_id)
    if not user:
        return None, jsonify({"error": "User not found"}), 404

    return user.company_id or user.id, None, None

def chatbot_to_dict(chatbot: ChatbotConfig) -> dict:
    """
    Converts a ChatbotConfig instance into a dictionary.
    The model field holding the subscription value is now 'subscription_plan'.
    """
    return {
        "company_id": chatbot.company_id,
        "id": chatbot.id,
        "chatbot_id": chatbot.chatbot_id,
        "bot_name": chatbot.bot_name,
        "purpose": chatbot.purpose,
        "goal": chatbot.goal,
        "role": chatbot.role,
        "subscription_plan": chatbot.subscription_plan,  # unified field
        "configuration": chatbot.configuration,
        "knowledge_base": chatbot.knowledge_base,
        "version": chatbot.version,
        "last_trained_at": chatbot.last_trained_at.isoformat() if chatbot.last_trained_at else None
    }

@admin_bp.route('/chatbots', methods=['GET'])
def list_chatbots():
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code
    try:
        chatbots = ChatbotConfig.query.filter_by(company_id=company_id).all()
        data = [chatbot_to_dict(c) for c in chatbots]
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/chatbots/<int:chatbot_id>', methods=['GET'])
def get_chatbot(chatbot_id):
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code
    try:
        chatbot = ChatbotConfig.query.get(chatbot_id)
        if not chatbot or chatbot.company_id != company_id:
            return jsonify({"error": "Chatbot not found for your company"}), 404
        return jsonify(chatbot_to_dict(chatbot)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/chatbots', methods=['POST'])
def create_chatbot():
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code

    # Ensure only one chatbot exists per company.
    existing = ChatbotConfig.query.filter_by(company_id=company_id).first()
    if existing:
        return jsonify({"error": f"A chatbot already exists for company {company_id}. Only one chatbot allowed."}), 400

    content_type = request.content_type or ""
    try:
        from users.models import User
        user_obj = User.query.filter((User.company_id == company_id) | (User.id == company_id)).first()

        if content_type.startswith("multipart/form-data"):
            form_data = request.form.to_dict()
            bot_name = form_data.get("bot_name")
            purpose = form_data.get("purpose")
            goal = form_data.get("goal")
            role = form_data.get("role")
            # Use subscription_plan from the request if provided; otherwise, fallback on the User's plan.
            subscription_plan = form_data.get("subscription_plan")
            if not subscription_plan or str(subscription_plan).strip() == "":
                subscription_plan = user_obj.subscription_plan or "basic"
            
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
                upload_folder = os.path.join("static", "uploads", "training_data")
                os.makedirs(upload_folder, exist_ok=True)
                extension = os.path.splitext(kb_file.filename)[1].lower()
                filename = f"training_{uuid.uuid4().hex}{extension}"
                file_path_on_disk = os.path.join(upload_folder, filename)
                kb_file.save(file_path_on_disk)
                faqs = []
                if extension in [".jsonl", ".json"]:
                    with open(file_path_on_disk, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    obj = json.loads(line)
                                    faqs.append(obj)
                                except:
                                    pass
                    knowledge_base["faqs"] = faqs
                elif extension == ".csv":
                    with open(file_path_on_disk, "r", encoding="utf-8") as csvfile:
                        reader = csv.reader(csvfile)
                        for row in reader:
                            if len(row) >= 2:
                                faqs.append({"question": row[0], "answer": row[1]})
                    knowledge_base["faqs"] = faqs

            new_chatbot = ChatbotConfig(
                company_id=company_id,
                chatbot_id=str(company_id),
                bot_name=bot_name,
                purpose=purpose,
                goal=goal,
                role=role,
                subscription_plan=subscription_plan,
                configuration=configuration,
                knowledge_base=knowledge_base,
                version=1,
                last_trained_at=datetime.utcnow()
            )
            db.session.add(new_chatbot)
            db.session.commit()
            return jsonify(chatbot_to_dict(new_chatbot)), 201

        elif content_type.startswith("application/json"):
            data = request.get_json()
            if not data:
                return jsonify({"error": "Missing JSON body"}), 400

            bot_name = data.get("bot_name")
            purpose = data.get("purpose")
            goal = data.get("goal")
            role = data.get("role")
            subscription_plan = data.get("subscription_plan")
            if not subscription_plan or str(subscription_plan).strip() == "":
                subscription_plan = user_obj.subscription_plan or "basic"
            configuration = data.get("configuration", {})
            configuration["purpose"] = purpose
            configuration["goal"] = goal
            configuration["role"] = role
            knowledge_base = data.get("knowledge_base", {})

            new_chatbot = ChatbotConfig(
                company_id=company_id,
                chatbot_id=str(company_id),
                bot_name=bot_name,
                purpose=purpose,
                goal=goal,
                role=role,
                subscription_plan=subscription_plan,
                configuration=configuration,
                knowledge_base=knowledge_base,
                version=1,
                last_trained_at=datetime.utcnow()
            )
            db.session.add(new_chatbot)
            db.session.commit()
            return jsonify(chatbot_to_dict(new_chatbot)), 201
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415

    except Exception as e:
        return jsonify({"error": "Error creating chatbot", "details": str(e)}), 500

@admin_bp.route('/chatbots/<int:chatbot_id>', methods=['PUT'])
def update_chatbot(chatbot_id):
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code

    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot or chatbot.company_id != company_id:
        return jsonify({"error": "Chatbot not found for your company"}), 404

    content_type = request.content_type or ""
    try:
        from users.models import User
        user_obj = User.query.filter((User.company_id == company_id) | (User.id == company_id)).first()

        if content_type.startswith("multipart/form-data"):
            form_data = request.form.to_dict()
            bot_name = form_data.get("bot_name", chatbot.bot_name)
            purpose = form_data.get("purpose", chatbot.purpose)
            goal = form_data.get("goal", chatbot.goal)
            role = form_data.get("role", chatbot.role)
            subscription_plan = form_data.get("subscription_plan", chatbot.subscription_plan)
            if not subscription_plan or str(subscription_plan).strip() == "":
                subscription_plan = user_obj.subscription_plan or "basic"
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
                upload_folder = os.path.join("static", "uploads", "training_data")
                os.makedirs(upload_folder, exist_ok=True)
                extension = os.path.splitext(kb_file.filename)[1].lower()
                filename = f"training_{uuid.uuid4().hex}{extension}"
                file_path_on_disk = os.path.join(upload_folder, filename)
                kb_file.save(file_path_on_disk)
                faqs = []
                if extension in [".jsonl", ".json"]:
                    with open(file_path_on_disk, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    obj = json.loads(line)
                                    faqs.append(obj)
                                except:
                                    pass
                    new_kb["faqs"] = faqs
                elif extension == ".csv":
                    with open(file_path_on_disk, "r", encoding="utf-8") as csvfile:
                        reader = csv.reader(csvfile)
                        for row in reader:
                            if len(row) >= 2:
                                faqs.append({"question": row[0], "answer": row[1]})
                    new_kb["faqs"] = faqs
            chatbot.bot_name = bot_name
            chatbot.purpose = purpose
            chatbot.goal = goal
            chatbot.role = role
            chatbot.subscription_plan = subscription_plan
            chatbot.configuration = new_config
            chatbot.knowledge_base = new_kb
            chatbot.version = (chatbot.version or 1) + 1
            chatbot.last_trained_at = datetime.utcnow()
            db.session.commit()
            return jsonify(chatbot_to_dict(chatbot)), 200

        elif content_type.startswith("application/json"):
            data = request.get_json()
            if not data:
                return jsonify({"error": "Missing JSON body"}), 400
            chatbot.bot_name = data.get("bot_name", chatbot.bot_name)
            chatbot.purpose = data.get("purpose", chatbot.purpose)
            chatbot.goal = data.get("goal", chatbot.goal)
            chatbot.role = data.get("role", chatbot.role)
            subscription_plan = data.get("subscription_plan", chatbot.subscription_plan)
            if not subscription_plan or str(subscription_plan).strip() == "":
                subscription_plan = user_obj.subscription_plan or "basic"
            chatbot.subscription_plan = subscription_plan
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
            db.session.commit()
            return jsonify(chatbot_to_dict(chatbot)), 200
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update chatbot", "details": str(e)}), 500

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

@admin_bp.route('/chatbots/dashboard', methods=['GET'])
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
