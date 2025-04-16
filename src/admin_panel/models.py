from core.database import db
from datetime import datetime
import uuid

class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved, closed
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    category = db.Column(db.String(50))
    assigned_to = db.Column(db.Integer, db.ForeignKey('admin_users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='support_tickets')
    company = db.relationship('Company', backref='support_tickets')
    admin = db.relationship('AdminUser', backref='assigned_tickets')
    messages = db.relationship('SupportMessage', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('SupportAttachment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.ticket_number:
            self.ticket_number = f"TKT-{uuid.uuid4().hex[:8].upper()}"

class SupportMessage(db.Model):
    __tablename__ = 'support_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False)  # 'user' or 'admin'
    sender_id = db.Column(db.Integer, nullable=False)  # user_id or admin_id
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_internal = db.Column(db.Boolean, default=False)  # For internal notes visible only to admins
    
    # Relationships
    attachments = db.relationship('MessageAttachment', backref='message', lazy='dynamic', cascade='all, delete-orphan')

class SupportAttachment(db.Model):
    __tablename__ = 'support_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)  # Size in bytes
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, nullable=False)  # user_id or admin_id
    uploader_type = db.Column(db.String(10), nullable=False)  # 'user' or 'admin'

class MessageAttachment(db.Model):
    __tablename__ = 'message_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('support_messages.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)  # Size in bytes
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Chatbot(db.Model):
    __tablename__ = 'chatbots'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    version = db.Column(db.String(20), default='1.0.0')
    plan = db.Column(db.String(20), default='basic')  # basic, pro, enterprise
    role = db.Column(db.String(100))  # e.g., Customer Support, Sales Assistant
    purpose = db.Column(db.Text)  # Main purpose of the chatbot
    goal = db.Column(db.Text)  # Specific goals to achieve
    status = db.Column(db.String(20), default='active')  # active, inactive, maintenance
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = db.relationship('Company', backref='chatbots')
    messages = db.relationship('Message', backref='chatbot', lazy='dynamic')

class KnowledgeBase(db.Model):
    __tablename__ = 'knowledge_base'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    status = db.Column(db.String(20), default='active')  # active, inactive, draft
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = db.relationship('Company', backref='knowledge_base')

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbots.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text)
    response_time = db.Column(db.Float)  # Response time in seconds
    feedback = db.Column(db.String(20))  # positive, negative, neutral
    topic = db.Column(db.String(100))  # Main topic of the conversation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='messages') 