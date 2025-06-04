from flask import Blueprint, request, jsonify, current_app, session, redirect, send_from_directory, send_file
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime, timedelta
from core.database import db
from admin_panel.models import SupportTicket, SupportMessage, MessageAttachment, KnowledgeBase, Chatbot, Message
from companies.models import Company, CompanyFeatureSettings
from admin.decorators import require_admin_role, require_admin_permission
from admin.models import AdminRole, AdminPermission, AdminUser
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import desc, func
from sqlalchemy.sql import text
from core.utils import verify_jwt
from users.models import User  # For accessing client data
from werkzeug.security import check_password_hash, generate_password_hash
import io
import csv
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

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
            attachment = MessageAttachment(
                ticket_id=ticket_id,
                filename=filename,
                file_path=relative_path,
                file_type=file.content_type,
                file_size=os.path.getsize(file_path)
            )
        
        db.session.add(attachment)
        return attachment
    return None

@support.route('/tickets', methods=['GET'])
def get_tickets():
    try:
        # Get company ID from user's token
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        # Get tickets for the user's company
        tickets = SupportTicket.query.filter_by(company_id=user.company_id).order_by(SupportTicket.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'tickets': [{
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'remarks': ticket.remarks,
                'subject': ticket.subject,
                'topic': ticket.topic,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'details': ticket.details,
                'attachments': [{
                    'filename': att.file_name,
                    'file_path': att.file_path
                } for att in ticket.attachments]
            } for ticket in tickets]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error in get_tickets: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch tickets',
            'details': str(e)
        }), 400

@support.route('/tickets', methods=['POST'])
def create_ticket():
    try:
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        # Check if user has a valid company_id
        if not user.company_id:
            return jsonify({'error': 'Your account is not properly associated with a company. Please contact support.'}), 400
            
        # Verify the company exists
        company = Company.query.get(user.company_id)
        if not company:
            current_app.logger.warning(
                f"User {user.id} with company_id {user.company_id} has no Company record; creating stub Company."
            )
            stub_company = Company(
                id=user.company_id,
                name=f"{user.company_name or user.user_name}'s Company",
                email=f"company{user.company_id}@example.com"
            )
            db.session.add(stub_company)
            db.session.commit()
            company = stub_company

        # Handle form data with file upload
        subject = request.form.get('subject')
        topic = request.form.get('topic')
        details = request.form.get('details')
        
        if not subject or not topic or not details:
            return jsonify({'error': 'Missing required fields'}), 400
            
        try:
            # Create the ticket
            ticket = SupportTicket(
                company_id=user.company_id,
                user_id=user.id,
                subject=subject,
                topic=topic,
                details=details,
                status='open'
            )
            
            db.session.add(ticket)
            db.session.commit()
            
            # Handle file upload if present
            if 'media' in request.files:
                file = request.files['media']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{user.id}_{uuid.uuid4().hex}_{filename}"
                    
                    # Create uploads directory if it doesn't exist
                    uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'support')
                    if not os.path.exists(uploads_dir):
                        os.makedirs(uploads_dir)
                    
                    file_path = os.path.join(uploads_dir, unique_filename)
                    file.save(file_path)
                    
                    # Use a relative path for storage in the database
                    relative_path = f"/static/uploads/support/{unique_filename}"
                    
                    attachment = MessageAttachment(
                        ticket_id=ticket.id,
                        file_path=relative_path,
                        file_name=filename,
                        file_type=file.content_type
                    )
                    
                    db.session.add(attachment)
                    db.session.commit()
            
            return jsonify({
                'success': True,
                'ticket': {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'remarks': ticket.remarks,
                    'subject': ticket.subject,
                    'topic': ticket.topic,
                    'status': ticket.status,
                    'created_at': ticket.created_at.isoformat(),
                    'details': ticket.details
                }
            }), 201
        except Exception as db_error:
            db.session.rollback()
            current_app.logger.error(f"Database error creating ticket: {str(db_error)}")
            raise db_error
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating support ticket: {str(e)}")
        
        # Check for foreign key violation
        if 'ForeignKeyViolation' in str(e):
            if 'company_id' in str(e):
                return jsonify({'error': 'Your account is not properly associated with a company. Please contact support for assistance.'}), 400
            elif 'user_id' in str(e):
                return jsonify({'error': 'User account validation failed. Please contact support for assistance.'}), 400
            else:
                return jsonify({'error': 'Database constraint error. Please contact support and provide this error message.'}), 400
        
        return jsonify({'error': 'An error occurred while submitting your ticket. Please try again later.'}), 400

@support.route('/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    try:
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        ticket = SupportTicket.query.filter_by(id=ticket_id, company_id=user.company_id).first()
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
            
        # Get ticket messages and attachments
        messages = SupportMessage.query.filter_by(ticket_id=ticket.id).order_by(SupportMessage.created_at.asc()).all()
        attachments = MessageAttachment.query.filter_by(ticket_id=ticket.id).all()
        
        return jsonify({
            'success': True,
            'ticket': {
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'remarks': ticket.remarks,
                'subject': ticket.subject,
                'topic': ticket.topic,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'details': ticket.details,
                'messages': [{
                    'id': msg.id,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat(),
                    'is_admin': msg.is_admin
                } for msg in messages],
                'attachments': [{
                    'id': att.id,
                    'file_name': att.file_name,
                    'file_type': att.file_type,
                    'created_at': att.created_at.isoformat()
                } for att in attachments]
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@support.route('/tickets/<int:ticket_id>/messages', methods=['POST'])
def add_ticket_message(ticket_id):
    try:
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        ticket = SupportTicket.query.filter_by(id=ticket_id, company_id=user.company_id).first()
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
            
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'error': 'Missing message content'}), 400
            
        message = SupportMessage(
            ticket_id=ticket.id,
            content=data['content'],
            is_admin=False
        )
        
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
                'is_admin': message.is_admin
            }
        }), 201
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

@admin_panel.route('/chatbots', methods=['GET'])
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
                'name': chatbot.name,
                'version': chatbot.version,
                'status': chatbot.status,
                'total_messages': chatbot.total_messages,
                'satisfaction_rate': chatbot.satisfaction_rate
            } for chatbot in chatbots]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in get_chatbots: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@admin_panel.route('/support/tickets', methods=['GET'])
@login_required
def get_support_tickets():
    try:
        # Get all tickets for super admin, or company-specific for other admins
        if current_user.role.name == AdminRole.SUPER_ADMIN.value:
            tickets = SupportTicket.query.all()
        else:
            if not current_user.company_id:
                return jsonify({'error': 'Company not assigned to admin user'}), 400
            tickets = SupportTicket.query.filter_by(company_id=current_user.company_id).all()
        
        # Process tickets to improve company name display
        processed_tickets = []
        for ticket in tickets:
            company_name = None
            if ticket.company:
                # Special case for company ID 6 which should be 'My Moving Journey'
                if ticket.company_id == 6:
                    company_name = "My Moving Journey"
                # If company name is generic (like 'Company 6'), use user info instead
                elif ticket.company.name and ticket.company.name.startswith('Company '):
                    if ticket.user and ticket.user.company_name:
                        company_name = ticket.user.company_name
                    elif ticket.user and ticket.user.user_name:
                        company_name = f"{ticket.user.user_name}'s Company"
                    else:
                        company_name = ticket.company.name
                else:
                    company_name = ticket.company.name
            
            processed_tickets.append({
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'remarks': ticket.remarks,
                'subject': ticket.subject,
                'details': ticket.details,
                'topic': ticket.topic,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
                'company_name': company_name,
                'user_name': ticket.user.user_name if ticket.user else None,
                'user_email': ticket.user.user_email if ticket.user else None,
                'attachments': [{
                    'filename': att.file_name,
                    'file_path': att.file_path
                } for att in ticket.attachments]
            })
        
        return jsonify({
            'tickets': processed_tickets
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in get_support_tickets: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_panel.route('/knowledge-base', methods=['GET'])
@login_required
def get_knowledge_base():
    try:
        # Get all knowledge base items for super admin, or company-specific for other admins
        if current_user.role.name == AdminRole.SUPER_ADMIN.value:
            items = KnowledgeBase.query.all()
        else:
            if not current_user.company_id:
                return jsonify({'error': 'Company not assigned to admin user'}), 400
            items = KnowledgeBase.query.filter_by(company_id=current_user.company_id).all()
        
        return jsonify({
            'items': [{
                'id': item.id,
                'title': item.title,
                'content': item.content,
                'category': item.category,
                'status': item.status,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat() if item.updated_at else None
            } for item in items]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in get_knowledge_base: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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

# Knowledge Base Routes
@admin_panel.route('/knowledge-base/faqs', methods=['GET'])
def get_faqs():
    try:
        # Get company ID from user's token
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        # Get FAQs for the user's company
        faqs = KnowledgeBase.query.filter_by(company_id=user.company_id).all()
        
        return jsonify({
            'success': True,
            'faqs': [{
                'id': faq.id,
                'question': faq.question,
                'answer': faq.answer,
                'category': faq.category
            } for faq in faqs]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error in get_faqs: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch FAQs',
            'details': str(e)
        }), 400

@support.route('/knowledge-base/faqs', methods=['POST'])
def create_faq():
    try:
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        data = request.get_json()
        if not data or 'question' not in data or 'answer' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
            
        faq = KnowledgeBase(
            company_id=user.company_id,
            question=data['question'],
            answer=data['answer'],
            category=data.get('category', 'General')
        )
        
        db.session.add(faq)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'faq': {
                'id': faq.id,
                'question': faq.question,
                'answer': faq.answer,
                'category': faq.category
            }
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@support.route('/knowledge-base/faqs/<int:faq_id>', methods=['PUT'])
def update_faq(faq_id):
    try:
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        faq = KnowledgeBase.query.filter_by(id=faq_id, company_id=user.company_id).first()
        if not faq:
            return jsonify({'error': 'FAQ not found'}), 404
            
        data = request.get_json()
        if 'question' in data:
            faq.question = data['question']
        if 'answer' in data:
            faq.answer = data['answer']
        if 'category' in data:
            faq.category = data['category']
            
        db.session.commit()
        
        return jsonify({
            'success': True,
            'faq': {
                'id': faq.id,
                'question': faq.question,
                'answer': faq.answer,
                'category': faq.category
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@support.route('/knowledge-base/faqs/<int:faq_id>', methods=['DELETE'])
def delete_faq(faq_id):
    try:
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        faq = KnowledgeBase.query.filter_by(id=faq_id, company_id=user.company_id).first()
        if not faq:
            return jsonify({'error': 'FAQ not found'}), 404
            
        db.session.delete(faq)
        db.session.commit()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400 