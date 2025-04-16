from flask import Blueprint, request, jsonify, current_app, session, redirect
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime, timedelta
from core.database import db
from models import SupportTicket, SupportMessage, SupportAttachment, MessageAttachment, Chatbot, KnowledgeBase, Company, Message
from admin.decorators import require_admin_role, require_admin_permission
from admin.models import AdminRole, AdminPermission, AdminUser
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import desc, func
from sqlalchemy.sql import text

support = Blueprint('support', __name__)
admin_panel = Blueprint('admin_panel', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, ticket_id=None, message_id=None):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        
        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
        
        file_path = os.path.join(uploads_dir, unique_filename)
        file.save(file_path)
        
        relative_path = f"/static/uploads/{unique_filename}"
        
        if message_id:
            attachment = MessageAttachment(
                message_id=message_id,
                filename=filename,
                file_path=relative_path,
                file_type=file.content_type,
                file_size=os.path.getsize(file_path)
            )
        else:
            attachment = SupportAttachment(
                ticket_id=ticket_id,
                filename=filename,
                file_path=relative_path,
                file_type=file.content_type,
                file_size=os.path.getsize(file_path)
            )
        
        db.session.add(attachment)
        return attachment
    return None

@support.route('/tickets', methods=['POST'])
@login_required
def create_ticket():
    try:
        data = request.form
        
        # Generate ticket number
        ticket_number = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        
        ticket = SupportTicket(
            ticket_number=ticket_number,
            user_id=current_user.id,
            company_id=current_user.company_id,
            subject=data['subject'],
            description=data['description'],
            category=data['category'],
            priority=data['priority'],
            status='open'
        )
        
        db.session.add(ticket)
        db.session.flush()  # Get the ticket ID
        
        # Handle file attachments
        files = request.files.getlist('attachments')
        for file in files:
            save_file(file, ticket_id=ticket.id)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Ticket created successfully',
            'ticket_number': ticket_number
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@support.route('/tickets', methods=['GET'])
@login_required
def get_tickets():
    try:
        # For regular users, show only their tickets
        if not current_user.is_admin:
            tickets = SupportTicket.query.filter_by(user_id=current_user.id)
        # For admins, show all tickets from their company
        else:
            tickets = SupportTicket.query.filter_by(company_id=current_user.company_id)
        
        tickets = tickets.order_by(desc(SupportTicket.created_at)).all()
        
        return jsonify({
            'tickets': [{
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'subject': ticket.subject,
                'description': ticket.description,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'attachments': [{
                    'filename': att.filename,
                    'file_path': att.file_path
                } for att in ticket.attachments]
            } for ticket in tickets]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@support.route('/tickets/<ticket_number>/messages', methods=['GET'])
@login_required
def get_ticket_messages(ticket_number):
    try:
        ticket = SupportTicket.query.filter_by(ticket_number=ticket_number).first_or_404()
        
        # Check if user has access to this ticket
        if not current_user.is_admin and ticket.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        messages = SupportMessage.query.filter_by(ticket_id=ticket.id)\
            .order_by(SupportMessage.created_at).all()
        
        return jsonify({
            'ticket': {
                'subject': ticket.subject,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat()
            },
            'messages': [{
                'id': msg.id,
                'message': msg.message,
                'sender_type': msg.sender_type,
                'sender_id': msg.sender_id,
                'created_at': msg.created_at.isoformat(),
                'attachments': [{
                    'filename': att.filename,
                    'file_path': att.file_path
                } for att in msg.attachments]
            } for msg in messages]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@support.route('/tickets/<ticket_number>/messages', methods=['POST'])
@login_required
def add_ticket_message(ticket_number):
    try:
        ticket = SupportTicket.query.filter_by(ticket_number=ticket_number).first_or_404()
        
        # Check if user has access to this ticket
        if not current_user.is_admin and ticket.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.form
        
        message = SupportMessage(
            ticket_id=ticket.id,
            message=data['message'],
            sender_type='admin' if current_user.is_admin else 'user',
            sender_id=current_user.id
        )
        
        db.session.add(message)
        db.session.flush()  # Get the message ID
        
        # Handle file attachments
        files = request.files.getlist('attachments')
        for file in files:
            save_file(file, message_id=message.id)
        
        # Update ticket status if admin responds
        if current_user.is_admin and ticket.status == 'open':
            ticket.status = 'in_progress'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Message added successfully',
            'message_id': message.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@support.route('/tickets/<ticket_number>/status', methods=['PUT'])
@require_admin_role(AdminRole.SUPER_ADMIN)
def update_ticket_status(ticket_number):
    try:
        ticket = SupportTicket.query.filter_by(ticket_number=ticket_number).first_or_404()
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'error': 'Status is required'}), 400
        
        valid_statuses = ['open', 'in_progress', 'resolved', 'closed']
        if data['status'] not in valid_statuses:
            return jsonify({'error': 'Invalid status'}), 400
        
        ticket.status = data['status']
        db.session.commit()
        
        return jsonify({
            'message': 'Ticket status updated successfully',
            'status': ticket.status
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@admin_panel.route('/chatbot/stats', methods=['GET'])
@login_required
def get_chatbot_stats():
    try:
        # Get all chatbots for super admin, or company-specific for other admins
        if current_user.role.name == AdminRole.SUPER_ADMIN.value:
            chatbots = Chatbot.query.all()
        else:
            chatbots = Chatbot.query.filter_by(company_id=current_user.company_id).all()
            
        chatbot_ids = [chatbot.id for chatbot in chatbots]
        
        # Calculate statistics for the last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Get total conversations
        total_conversations = db.session.query(func.count(Message.id)).\
            filter(Message.chatbot_id.in_(chatbot_ids)).\
            filter(Message.created_at >= thirty_days_ago).\
            scalar() or 0
        
        # Get success rate (messages with positive feedback)
        successful_conversations = db.session.query(func.count(Message.id)).\
            filter(Message.chatbot_id.in_(chatbot_ids)).\
            filter(Message.feedback == 'positive').\
            filter(Message.created_at >= thirty_days_ago).\
            scalar() or 0
        
        success_rate = (successful_conversations / total_conversations * 100) if total_conversations > 0 else 0
        
        # Get average response time
        avg_response_time = db.session.query(func.avg(Message.response_time)).\
            filter(Message.chatbot_id.in_(chatbot_ids)).\
            filter(Message.created_at >= thirty_days_ago).\
            scalar() or 0
        
        # Get user satisfaction (based on feedback)
        positive_feedback = db.session.query(func.count(Message.id)).\
            filter(Message.chatbot_id.in_(chatbot_ids)).\
            filter(Message.feedback == 'positive').\
            filter(Message.created_at >= thirty_days_ago).\
            scalar() or 0
        
        total_feedback = db.session.query(func.count(Message.id)).\
            filter(Message.chatbot_id.in_(chatbot_ids)).\
            filter(Message.feedback != None).\
            filter(Message.created_at >= thirty_days_ago).\
            scalar() or 0
        
        user_satisfaction = (positive_feedback / total_feedback * 100) if total_feedback > 0 else 0
        
        # Get conversations over time data
        conversations_data = db.session.query(
            func.date(Message.created_at).label('date'),
            func.count(Message.id).label('count')
        ).\
        filter(Message.chatbot_id.in_(chatbot_ids)).\
        filter(Message.created_at >= thirty_days_ago).\
        group_by('date').\
        order_by('date').all()
        
        conversations_labels = [str(record.date) for record in conversations_data]
        conversations_values = [record.count for record in conversations_data]
        
        # Get top conversation topics
        topics_data = db.session.query(
            Message.topic,
            func.count(Message.id).label('count')
        ).\
        filter(Message.chatbot_id.in_(chatbot_ids)).\
        filter(Message.created_at >= thirty_days_ago).\
        group_by(Message.topic).\
        order_by(text('count DESC')).\
        limit(5).all()
        
        topics_labels = [record.topic for record in topics_data]
        topics_values = [record.count for record in topics_data]
        
        return jsonify({
            'totalConversations': total_conversations,
            'successRate': round(success_rate, 2),
            'avgResponseTime': round(avg_response_time, 2),
            'userSatisfaction': round(user_satisfaction, 2),
            'conversationsData': {
                'labels': conversations_labels,
                'values': conversations_values
            },
            'topicsData': {
                'labels': topics_labels,
                'values': topics_values
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@admin_panel.route('/chatbot/list', methods=['GET'])
@login_required
def get_chatbots():
    try:
        # Get all chatbots for super admin, or company-specific for other admins
        if current_user.role.name == AdminRole.SUPER_ADMIN.value:
            chatbots = Chatbot.query.all()
        else:
            if not current_user.company_id:
                return jsonify({'error': 'Company not assigned to admin user'}), 400
            chatbots = Chatbot.query.filter_by(company_id=current_user.company_id).all()
        
        return jsonify({
            'chatbots': [{
                'id': chatbot.id,
                'company_name': chatbot.company.name if chatbot.company else 'N/A',
                'name': chatbot.name,
                'version': chatbot.version,
                'plan': chatbot.plan,
                'role': chatbot.role,
                'purpose': chatbot.purpose,
                'goal': chatbot.goal
            } for chatbot in chatbots]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@admin_panel.route('/knowledge-base', methods=['GET'])
@login_required
def get_knowledge_base():
    try:
        # Get all knowledge base items for super admin, or company-specific for other admins
        if current_user.role.name == AdminRole.SUPER_ADMIN.value:
            knowledge_items = KnowledgeBase.query.all()
        else:
            if not current_user.company_id:
                return jsonify({'error': 'Company not assigned to admin user'}), 400
            knowledge_items = KnowledgeBase.query.filter_by(company_id=current_user.company_id).all()
        
        return jsonify({
            'items': [{
                'id': item.id,
                'title': item.title,
                'category': item.category,
                'last_updated': item.updated_at.isoformat(),
                'status': item.status
            } for item in knowledge_items]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@admin_panel.route('/logout', methods=['POST'])
@login_required
def logout():
    try:
        logout_user()
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@admin_panel.route('/check-auth', methods=['GET'])
def check_auth():
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'admin': {
                'id': current_user.id,
                'name': current_user.name,
                'email': current_user.email,
                'role': current_user.role,
                'permissions': current_user.permissions
            }
        }), 200
    return jsonify({'authenticated': False}), 401 