from model_inference import run_inference_openai
from model_training import train_model
from models import ChatbotConfig
from database import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.mutable import MutableDict
from flask import Blueprint, request, jsonify
from users.models import User
from core.utils import verify_jwt
from core.utils import get_jwt
from core.utils import get_user
from core.utils import get_chatbot
from core.utils import get_chat_session
from core.utils import get_chat_message
from core.utils import get_chat
from core.utils import get_train_data
from core.utils import get_chatbot_interaction
from core.utils import get_chatbot_config
from core.utils import get_chatbot_configs
from core.utils import get_chats
from core.utils import get_train_data
from core.utils import get_train_data
from core.utils import get_chatbot_interactions

session_bp = Blueprint('session', __name__)
db.create_all()
# db.session.commit()
# db.session.close()


@session_bp.route('/session', methods=['POST'])
def create_session():
    data = request.json
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header missing"}), 401
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401
    user = get_user(payload.get("user_id"))
    if not user:
        return jsonify({"error": "User not found"}), 404
    company_id = user.company_id or user.id
    chatbot = get_chatbot(company_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    session = ChatSession(user_id=user.id, chatbot_id=chatbot.id)
    db.session.add(session)
    db.session.commit()
    return jsonify({
        "session_id": session.id,
        "created_at": session.created_at.isoformat(),
        "chatbot_id": chatbot.id
    }), 201


@session_bp.route('/session/<int:session_id>/message', methods=['POST'])
def create_message(session_id):
    data = request.json
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header missing"}), 401
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401
    user = get_user(payload.get("user_id"))
    if not user:
        return jsonify({"error": "User not found"}), 404
    session = get_chat_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    chatbot = get_chatbot(session.chatbot_id)
    if not chatbot:
        return jsonify({"error": "Chatbot not found"}), 404
    if data.get("sender") not in ["user", "bot"]:
        return jsonify({"error": "Invalid sender"}), 400
    message = ChatMessage(
        session_id=session.id,
        sender=data.get("sender"),
        message=data.get("message")
    )
    db.session.add(message)
    db.session.commit()
    return jsonify({
        "message_id": message.id,
        "created_at": message.created_at.isoformat(),
        "sender": message.sender,
        "message": message.message
    }), 201

