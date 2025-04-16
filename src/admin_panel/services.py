"""
Admin Panel Services

Provides business logic for managing chatbot configurations.
Handles CRUD operations, knowledge base merging, re-training, and conversion to dictionary format.
"""

from chatbot.models import ChatbotConfig
from core.database import db
from chatbot import model_training, data_processing

def chatbot_to_dict(chatbot: ChatbotConfig) -> dict:
    return {
        "id": chatbot.id,
        "company_id": chatbot.company_id,
        "configuration": chatbot.configuration,
        "purpose": chatbot.purpose,
        "goal": chatbot.goal,
        "role": chatbot.role,
        "payment_plan": chatbot.payment_plan,
        "version": chatbot.version,
        "knowledge_base": chatbot.knowledge_base,
        "last_trained_at": chatbot.last_trained_at.isoformat() if chatbot.last_trained_at else None,
    }

def get_all_chatbots(client_id: int = None):
    if client_id:
        return ChatbotConfig.query.filter_by(company_id=client_id).all()
    return ChatbotConfig.query.all()

def get_chatbot_by_id(chatbot_id: int):
    return ChatbotConfig.query.get(chatbot_id)

def create_chatbot(data: dict) -> ChatbotConfig:
    try:
        company_id = data.get("company_id")
        if not company_id:
            raise Exception("Company ID is required.")

        # Check if a chatbot already exists for this company.
        existing = ChatbotConfig.query.filter_by(company_id=company_id).first()
        if existing:
            raise Exception("A chatbot already exists for this company. Only one chatbot is allowed per company.")

        configuration = data.get("configuration", {})
        purpose = data.get("purpose")
        goal = data.get("goal")
        role = data.get("role")
        payment_plan = data.get("payment_plan", "free_trial")
        knowledge_base = data.get("knowledge_base", {})

        processed_kb = data_processing.preprocess_knowledge_base(knowledge_base) if knowledge_base else {}
        trained_model = model_training.train_model(processed_kb, configuration) if processed_kb else None

        chatbot = ChatbotConfig(
            company_id=company_id,
            configuration=configuration,
            purpose=purpose,
            goal=goal,
            role=role,
            payment_plan=payment_plan,
            knowledge_base=processed_kb,
            trained_model=trained_model
        )
        db.session.add(chatbot)
        db.session.commit()
        return chatbot
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error creating chatbot: {e}")


def update_chatbot_config(chatbot_id: int, data: dict) -> ChatbotConfig:
    chatbot = get_chatbot_by_id(chatbot_id)
    if not chatbot:
        return None

    try:
        chatbot.configuration = data.get("configuration", chatbot.configuration)
        chatbot.purpose = data.get("purpose", chatbot.purpose)
        chatbot.goal = data.get("goal", chatbot.goal)
        chatbot.role = data.get("role", chatbot.role)
        chatbot.payment_plan = data.get("payment_plan", chatbot.payment_plan)

        new_kb = data.get("knowledge_base")
        if new_kb:
            processed_new_kb = data_processing.preprocess_knowledge_base(new_kb)
            if chatbot.knowledge_base and isinstance(chatbot.knowledge_base, dict):
                existing_faqs = chatbot.knowledge_base.get("faqs", [])
                new_faqs = processed_new_kb.get("faqs", [])
                merged_faqs = existing_faqs + new_faqs
                chatbot.knowledge_base["faqs"] = merged_faqs
            else:
                chatbot.knowledge_base = processed_new_kb

            chatbot.trained_model = model_training.train_model(chatbot.knowledge_base, chatbot.configuration)
        
        db.session.commit()
        return chatbot
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error updating chatbot: {e}")

def delete_chatbot(chatbot_id: int) -> bool:
    chatbot = get_chatbot_by_id(chatbot_id)
    if not chatbot:
        return False
    try:
        db.session.delete(chatbot)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error deleting chatbot: {e}")

def retrain_chatbot(chatbot_id: int, new_knowledge_base: dict, new_config: dict = None) -> ChatbotConfig:
    chatbot = get_chatbot_by_id(chatbot_id)
    if not chatbot:
        return None
    try:
        if new_config:
            chatbot.configuration = new_config
            chatbot.purpose = new_config.get("purpose", chatbot.purpose)
            chatbot.goal = new_config.get("goal", chatbot.goal)
            chatbot.role = new_config.get("role", chatbot.role)
            chatbot.payment_plan = new_config.get("payment_plan", chatbot.payment_plan)
        
        processed_kb = data_processing.preprocess_knowledge_base(new_knowledge_base)
        chatbot.knowledge_base = processed_kb
        chatbot.trained_model = model_training.train_model(processed_kb, chatbot.configuration)
        
        db.session.commit()
        return chatbot
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error retraining chatbot: {e}")
