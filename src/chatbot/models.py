"""
Chatbot Models

Defines the models for chatbot configuration, interactions, chat logs, training data, and sessions.
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.mutable import MutableDict  # This enables tracking of in-place changes
from core.database import db

class ChatbotConfig(db.Model):
    __tablename__ = 'chatbot_configs'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    # External chatbot identifier if needed.
    bot_name = db.Column(db.String(255), nullable=True)
    chatbot_id = db.Column(db.String(64), nullable=True)
    role = db.Column(db.String(255), nullable=True)
    subscription_plan = db.Column(db.String(50), nullable=True)
    version = db.Column(db.Integer, default=1)
    configuration = db.Column(MutableDict.as_mutable(JSON), nullable=True)
    purpose = db.Column(db.String(255), nullable=True)
    goal = db.Column(db.String(255), nullable=True)
    knowledge_base = db.Column(MutableDict.as_mutable(JSON), nullable=True)
    trained_model = db.Column(db.LargeBinary, nullable=True)
    last_trained_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatbotConfig id={self.id} company_id={self.company_id}>"

class ChatbotInteraction(db.Model):
    __tablename__ = 'chatbot_interactions'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    chatbot_id = db.Column(db.Integer, nullable=False)
    bot_name = db.Column(db.String(255), nullable=True)
    chat_id = db.Column(db.String(64), nullable=False)
    messages = db.Column(JSON, nullable=True)  # List of messages (conversation log)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatbotInteraction chat_id={self.chat_id}>"

class Chat(db.Model):
    __tablename__ = 'chats'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    chatbot_id = db.Column(db.Integer, nullable=False)
    chat_id = db.Column(db.String(64), nullable=False)
    bot_name = db.Column(db.String(255), nullable=True)
    messages = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Chat chat_id={self.chat_id}>"

class Train(db.Model):
    __tablename__ = 'train_data'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    chatbot_id = db.Column(db.Integer, nullable=False)
    bot_name = db.Column(db.String(255), nullable=True)
    faqs = db.Column(JSON, nullable=True)    # FAQs used for training.
    queries = db.Column(JSON, nullable=True) # Past queries for analysis.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TrainData chatbot_id={self.chatbot_id}>"

# Add ChatSession model here so that it can be imported in views
class ChatSession(db.Model):
    __tablename__ = "chat_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    chatbot_id = db.Column(db.Integer, db.ForeignKey("chatbot_configs.id"), nullable=True)
    bot_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    ended = db.Column(db.Boolean, default=False)
    # Relationship to access associated messages
    messages = db.relationship("ChatMessage", backref="session", lazy=True, cascade="all, delete-orphan")

class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    bot_name = db.Column(db.String(255), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    sender = db.Column(db.String(50), nullable=False)  # Expected: "user" or "bot"
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
