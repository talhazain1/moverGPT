# chatbot/session_views.py

from flask import Blueprint, request, jsonify
from datetime import datetime
from core.database import db
from core.utils import verify_jwt
from chatbot.models import ChatSession, ChatMessage, ChatbotConfig
from users.models import User  # Make sure you can import the user
from companies.models import MovingParameters
from services.email_service import EmailService

session_bp = Blueprint('session', __name__)

@session_bp.route('/session', methods=['POST'])
def create_chat_session():
    """
    Creates a new chat session for the logged-in user,
    automatically associates it with the single chatbot for that user's company.
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
    
    # If this is a bot message and there's a response_time in the data, use it
    if sender == "bot" and "response_time" in data:
        chat_message.response_time = float(data["response_time"])
    
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
        # Send chat transcript email to staff
        try:
            user = User.query.get(session_obj.user_id)
            company_id = user.company_id or user.id
            params = MovingParameters.query.filter_by(company_id=company_id).first()
            if params and params.email_config:
                smtp_config = params.email_config.get("smtp", {})
                staff_email_addr = smtp_config.get("staff_email")
                if smtp_config and staff_email_addr:
                    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
                    transcript_lines = [f"{m.timestamp.isoformat()} {m.sender}: {m.message}" for m in messages]
                    transcript = "\n".join(transcript_lines)
                    subject = f"Chat Transcript for Session {session_id}"
                    body = f"Hello,\n\nHere is the transcript for chat session {session_id}:\n\n{transcript}"
                    email_service = EmailService(smtp_config)
                    success, err_msg = email_service.send_email(staff_email_addr, subject, body)
                    if success:
                        print(f"DEBUG: Chat transcript email sent to {staff_email_addr}")
                    else:
                        print(f"DEBUG: Failed to send chat transcript email: {err_msg}")
        except Exception as email_err:
            print(f"DEBUG: Error sending chat transcript email: {email_err}")
        return jsonify({"message": "Chat session ended"}), 200
    except Exception as e:
        db.session.rollback()
        print("DEBUG: Failed to end chat session:", e)
        return jsonify({"error": f"Failed to end session: {e}"}), 500

@session_bp.route('/message/<int:message_id>/feedback', methods=['POST'])
def submit_message_feedback(message_id):
    """
    Submit feedback for a specific message.
    Expects JSON: { "rating": 1-5, "feedback": "positive"|"negative"|"neutral" }
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Authorization header missing in submit_message_feedback")
        return jsonify({"error": "Authorization header missing"}), 401
    
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in submit_message_feedback")
        return jsonify({"error": "Invalid or expired token"}), 401
    
    data = request.get_json()
    if not data:
        print("DEBUG: Missing data in submit_message_feedback")
        return jsonify({"error": "No data provided"}), 400
    
    rating = data.get("rating")
    feedback_type = data.get("feedback")
    
    # Validate rating
    if rating is not None and (not isinstance(rating, int) or rating < 1 or rating > 5):
        print(f"DEBUG: Invalid rating value: {rating}")
        return jsonify({"error": "Rating must be an integer between 1 and 5"}), 400
    
    # Validate feedback type
    if feedback_type and feedback_type not in ["positive", "negative", "neutral"]:
        print(f"DEBUG: Invalid feedback type: {feedback_type}")
        return jsonify({"error": "Feedback type must be 'positive', 'negative', or 'neutral'"}), 400
    
    # Get the message
    message = ChatMessage.query.get(message_id)
    if not message:
        print(f"DEBUG: Message not found with id: {message_id}")
        return jsonify({"error": "Message not found"}), 404
    
    try:
        # Update the message with feedback
        old_feedback = message.feedback
        
        if rating is not None:
            message.rating = rating
        
        if feedback_type:
            message.feedback = feedback_type
        
        # Get the chatbot associated with this message
        chat_session = ChatSession.query.get(message.session_id)
        if chat_session and chat_session.chatbot_id:
            chatbot = ChatbotConfig.query.get(chat_session.chatbot_id)
            if chatbot:
                # Only update stats if feedback type has changed
                if feedback_type and feedback_type != old_feedback:
                    # If there was previous feedback, adjust counts accordingly
                    if old_feedback:
                        chatbot.total_feedback_count -= 1
                        if old_feedback == "positive":
                            chatbot.positive_feedback_count -= 1
                    
                    # Increment the total feedback count
                    chatbot.total_feedback_count += 1
                    
                    # If positive feedback, increment the positive count
                    if feedback_type == "positive":
                        chatbot.positive_feedback_count += 1
                    
                    # Update satisfaction rate
                    if chatbot.total_feedback_count > 0:
                        chatbot.satisfaction_rate = round((chatbot.positive_feedback_count / chatbot.total_feedback_count) * 100, 1)
                    else:
                        chatbot.satisfaction_rate = 0.0
                    
                    print(f"DEBUG: Updated chatbot statistics - positive_feedback_count: {chatbot.positive_feedback_count}, "
                          f"total_feedback_count: {chatbot.total_feedback_count}, satisfaction_rate: {chatbot.satisfaction_rate}")
        
        db.session.commit()
        print(f"DEBUG: Updated message {message_id} with rating: {rating}, feedback: {feedback_type}")
        
        return jsonify({
            "message": "Feedback submitted successfully",
            "message_id": message_id,
            "rating": message.rating,
            "feedback": message.feedback
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Failed to submit feedback: {e}")
        return jsonify({"error": f"Failed to submit feedback: {e}"}), 500

@session_bp.route('/chatbot/<int:chatbot_id>/recalculate-statistics', methods=['POST'])
def recalculate_chatbot_statistics(chatbot_id):
    """
    Recalculates all feedback statistics for a chatbot based on actual message feedback.
    This is useful for syncing statistics or after data migrations.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("DEBUG: Authorization header missing in recalculate_chatbot_statistics")
        return jsonify({"error": "Authorization header missing"}), 401
    
    token = auth_header.split(" ")[-1]
    payload = verify_jwt(token)
    if not payload:
        print("DEBUG: Invalid or expired token in recalculate_chatbot_statistics")
        return jsonify({"error": "Invalid or expired token"}), 401
    
    # TODO: Add permission check to ensure only admins or owners can do this
    
    chatbot = ChatbotConfig.query.get(chatbot_id)
    if not chatbot:
        print(f"DEBUG: Chatbot not found with id: {chatbot_id}")
        return jsonify({"error": "Chatbot not found"}), 404
    
    try:
        # Count all messages with feedback for this chatbot
        total_feedback = db.session.query(db.func.count(ChatMessage.id))\
            .join(ChatSession)\
            .filter(
                ChatSession.chatbot_id == chatbot_id,
                ChatMessage.feedback.isnot(None)
            ).scalar() or 0
        
        # Count positive feedback
        positive_feedback = db.session.query(db.func.count(ChatMessage.id))\
            .join(ChatSession)\
            .filter(
                ChatSession.chatbot_id == chatbot_id,
                ChatMessage.feedback == 'positive'
            ).scalar() or 0
        
        # Calculate satisfaction rate
        satisfaction_rate = 0.0
        if total_feedback > 0:
            satisfaction_rate = round((positive_feedback / total_feedback) * 100, 1)
        
        # Update the chatbot config
        chatbot.total_feedback_count = total_feedback
        chatbot.positive_feedback_count = positive_feedback
        chatbot.satisfaction_rate = satisfaction_rate
        
        db.session.commit()
        
        print(f"DEBUG: Recalculated statistics for chatbot {chatbot_id}: "
              f"total_feedback={total_feedback}, positive_feedback={positive_feedback}, "
              f"satisfaction_rate={satisfaction_rate}")
        
        return jsonify({
            "message": "Statistics recalculated successfully",
            "chatbot_id": chatbot_id,
            "total_feedback_count": total_feedback,
            "positive_feedback_count": positive_feedback,
            "satisfaction_rate": satisfaction_rate
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Failed to recalculate statistics: {e}")
        return jsonify({"error": f"Failed to recalculate statistics: {e}"}), 500
