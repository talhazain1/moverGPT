# chatbot/session_views.py

from flask import Blueprint, request, jsonify
from datetime import datetime
from core.database import db
from core.utils import verify_jwt
from chatbot.models import ChatSession, ChatMessage, ChatbotConfig
from users.models import User  # Make sure you can import the user

session_bp = Blueprint('session', __name__)

@session_bp.route('/session', methods=['POST'])
def create_chat_session():
    """
    Creates a new chat session for the logged-in user,
    automatically associates it with the single chatbot for that user’s company.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Authorization header missing in create_chat_session")
        return jsonify({"error": "Authorization header missing"}), 401
    
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in create_chat_session")
        return jsonify({"error": "Invalid or expired token"}), 401
    
    user_id = payload.get("user_id")
    if not user_id:
        print("DEBUG: user_id missing in token in create_chat_session")
        return jsonify({"error": "user_id missing in token"}), 400
    
    from users.models import User
    user = User.query.get(user_id)
    if not user:
        print("DEBUG: User not found for user_id =", user_id)
        return jsonify({"error": "User not found"}), 404
    
    company_id = user.company_id or user.id  # fallback if no separate company_id
    chatbot = ChatbotConfig.query.filter_by(company_id=company_id).first()
    chatbot_id = chatbot.id if chatbot else None
    
    session = ChatSession(user_id=user_id, chatbot_id=chatbot_id)
    try:
        db.session.add(session)
        db.session.commit()
        print("DEBUG: Created chat session with id =", session.id)
        return jsonify({
            "session_id": session.id,
            "created_at": session.created_at.isoformat(),
            "chatbot_id": chatbot_id
        }), 201
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to create chat session:", e)
        return jsonify({"error": f"Failed to create session: {e}"}), 500

@session_bp.route('/session/<int:session_id>/message', methods=['POST'])
def add_chat_message(session_id):
    """
    Adds a new message to the specified chat session.
    Expects JSON: { "sender": "user" or "bot", "message": "..." }
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Authorization header missing in add_chat_message")
        return jsonify({"error": "Authorization header missing"}), 401
    
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in add_chat_message")
        return jsonify({"error": "Invalid or expired token"}), 401
    
    data = request.get_json()
    if not data or "sender" not in data or "message" not in data:
        print("DEBUG: Missing sender or message in add_chat_message")
        return jsonify({"error": "Message and sender are required"}), 400
    
    sender = data["sender"]
    if sender not in ["user", "bot"]:
        print("DEBUG: Invalid sender:", sender)
        return jsonify({"error": "Sender must be 'user' or 'bot'"}), 400
    
    message_text = data["message"]
    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print("DEBUG: Chat session not found for id =", session_id)
        return jsonify({"error": "Chat session not found"}), 404
    
    chat_message = ChatMessage(session_id=session_id, sender=sender, message=message_text)
    try:
        db.session.add(chat_message)
        db.session.commit()
        print("DEBUG: Message added with id =", chat_message.id)
        
        # For additional debugging, count messages in this session after commit:
        count = ChatMessage.query.filter_by(session_id=session_id).count()
        print(f"DEBUG: Total messages in session {session_id}: {count}")
        
        return jsonify({
            "message": "Message added",
            "message_id": chat_message.id,
            "timestamp": chat_message.timestamp.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to add message:", e)
        return jsonify({"error": f"Failed to add message: {e}"}), 500

@session_bp.route('/session/<int:session_id>/messages', methods=['GET'])
def get_chat_messages(session_id):
    """
    Retrieves all messages for the specified chat session in chronological order.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Authorization header missing in get_chat_messages")
        return jsonify({"error": "Authorization header missing"}), 401
    
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in get_chat_messages")
        return jsonify({"error": "Invalid or expired token"}), 401
    
    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print("DEBUG: Chat session not found in get_chat_messages for session id =", session_id)
        return jsonify({"error": "Chat session not found"}), 404
    
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    messages_list = []
    for m in messages:
        messages_list.append({
            "id": m.id,
            "sender": m.sender,
            "message": m.message,
            "timestamp": m.timestamp.isoformat()
        })
    print(f"DEBUG: Retrieved {len(messages_list)} messages for session id {session_id}")
    return jsonify({
        "session_id": session_id,
        "messages": messages_list
    }), 200

@session_bp.route('/session/<int:session_id>/end', methods=['POST'])
def end_chat_session(session_id):
    """
    Marks the specified chat session as ended.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Authorization header missing in end_chat_session")
        return jsonify({"error": "Authorization header missing"}), 401
    
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in end_chat_session")
        return jsonify({"error": "Invalid or expired token"}), 401
    
    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        print("DEBUG: Chat session not found in end_chat_session for session id =", session_id)
        return jsonify({"error": "Chat session not found"}), 404
    
    session_obj.ended = True
    session_obj.updated_at = datetime.utcnow()
    try:
        db.session.commit()
        print("DEBUG: Ended chat session with id =", session_id)
        return jsonify({"message": "Chat session ended"}), 200
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to end chat session:", e)
        return jsonify({"error": f"Failed to end session: {e}"}), 500
