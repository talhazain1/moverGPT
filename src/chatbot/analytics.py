"""
Chatbot Analytics Module

Provides functions for logging interactions and retrieving usage statistics.
"""

from chatbot.models import ChatbotInteraction
from core.database import db

def log_interaction(company_id: int, chatbot_id: int, chat_id: str, user_input: str, bot_response: str):
    try:
        interaction = ChatbotInteraction(
            company_id=company_id,
            chatbot_id=chatbot_id,
            chat_id=chat_id,
            messages={"user": user_input, "bot": bot_response}
        )
        db.session.add(interaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error logging interaction: {e}")

def get_usage_statistics(company_id: int, chatbot_id: int) -> dict:
    try:
        total_interactions = ChatbotInteraction.query.filter_by(company_id=company_id, chatbot_id=chatbot_id).count()
        return {"total_interactions": total_interactions}
    except Exception as e:
        raise Exception(f"Error retrieving usage statistics: {e}")
