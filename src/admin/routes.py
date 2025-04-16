from flask import Blueprint, request, jsonify, send_from_directory, session, redirect, send_file, current_app
from core.database import db
from admin.models import AdminUser, AdminRole, AdminPermission, AdminRoleModel
from admin.decorators import require_admin_role, require_admin_permission
from core.utils import verify_jwt
from users.models import User  # For accessing client data
from werkzeug.security import check_password_hash, generate_password_hash
import os
import io
import csv
import logging
from datetime import datetime
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from models import SupportTicket, SupportAttachment
from core.database import db

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

@admin_bp.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Error in admin routes: {str(error)}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500

# Admin login route
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # If already logged in, redirect to dashboard
        if current_user.is_authenticated:
            return redirect('/admin/dashboard.html')
        return jsonify({'message': 'Please login'}), 200
        
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
            
        admin = AdminUser.query.filter_by(email=email).first()
        if not admin or not check_password_hash(admin.password_hash, password):
            return jsonify({'error': 'Invalid email or password'}), 401
            
        # Update last login time
        admin.last_login = datetime.utcnow()
        db.session.commit()
        
        # Login the user
        login_user(admin, remember=True)
        
        # Get the next URL from the query parameters
        next_url = request.args.get('next')
        if next_url:
            return jsonify({
                'message': 'Login successful',
                'redirect': next_url,
                'admin': {
                    'id': admin.id,
                    'name': admin.name,
                    'email': admin.email,
                    'role': admin.role.name if admin.role else None,
                    'permissions': admin.get_permissions()
                }
            }), 200
            
        return jsonify({
            'message': 'Login successful',
            'admin': {
                'id': admin.id,
                'name': admin.name,
                'email': admin.email,
                'role': admin.role.name if admin.role else None,
                'permissions': admin.get_permissions()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 400

# Check admin authentication
@admin_bp.route('/check-auth', methods=['GET'])
def check_auth():
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'admin': {
                'id': current_user.id,
                'name': current_user.name,
                'email': current_user.email,
                'role': current_user.role.name if current_user.role else None,
                'permissions': current_user.get_permissions()
            }
        }), 200
    return jsonify({'authenticated': False}), 401

# Admin logout
@admin_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    try:
        logout_user()
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Serve admin dashboard
@admin_bp.route('/dashboard')
def serve_dashboard():
    # Check if admin is logged in
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect('/admin/login.html')
    
    admin = AdminUser.query.get(admin_id)
    if not admin or not admin.is_active:
        return redirect('/admin/login.html')
    
    return send_from_directory('static/admin', 'dashboard.html')

# Dashboard stats
@admin_bp.route('/dashboard/stats')
@require_admin_role(AdminRole.SUPER_ADMIN)
def get_dashboard_stats():
    try:
        stats = {
            'totalCompanies': 0,
            'activeSubscriptions': 0,
            'pendingSupport': 0,
            'apiUsage': 0
        }
        
        # Get total number of companies
        stats['totalCompanies'] = db.session.query(db.func.count(User.id)).filter(
            User.company_name.isnot(None)
        ).scalar() or 0
        
        # Get active subscriptions
        stats['activeSubscriptions'] = db.session.query(db.func.count(User.id)).filter(
            User.subscription_status == 'active'
        ).scalar() or 0
        
        # Try to get support tickets if model exists
        try:
            from chatbot.models import SupportTicket
            stats['pendingSupport'] = db.session.query(db.func.count(SupportTicket.id)).filter(
                SupportTicket.status == 'pending'
            ).scalar() or 0
        except ImportError:
            logger.warning("SupportTicket model not available")
        
        # Try to get API usage if model exists
        try:
            from chatbot.models import ChatSession
            from datetime import datetime, timedelta
            last_24h = datetime.utcnow() - timedelta(hours=24)
            stats['apiUsage'] = db.session.query(db.func.count(ChatSession.id)).filter(
                ChatSession.created_at >= last_24h
            ).scalar() or 0
        except ImportError:
            logger.warning("ChatSession model not available")
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# Team Members Management
@admin_bp.route('/admins', methods=['GET', 'POST', 'PUT', 'DELETE'])
@require_admin_role(AdminRole.SUPER_ADMIN)
def manage_admins():
    if request.method == 'GET':
        admins = AdminUser.query.all()
        return jsonify({
            "admins": [{
                "id": admin.id,
                "email": admin.email,
                "name": admin.name,
                "role": admin.role.name if admin.role else None,
                "is_active": admin.is_active,
                "last_login": admin.last_login.isoformat() if admin.last_login else None
            } for admin in admins]
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        name = data.get('name')
        role = data.get('role')
        password = data.get('password')
        
        if not all([email, name, role, password]):
            return jsonify({'message': 'Missing required fields'}), 400
        
        # Check if email already exists
        if AdminUser.query.filter_by(email=email).first():
            return jsonify({'message': 'Email already exists'}), 400
        
        # Get role
        admin_role = AdminRoleModel.query.filter_by(name=role).first()
        if not admin_role:
            return jsonify({'message': 'Invalid role'}), 400
        
        # Create new admin
        admin = AdminUser(
            email=email,
            name=name,
            password_hash=generate_password_hash(password),
            role_id=admin_role.id,
            is_active=True
        )
        
        try:
            db.session.add(admin)
            db.session.commit()
            return jsonify({'message': 'Admin created successfully'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500
    
    elif request.method == 'PUT':
        data = request.get_json()
        admin_id = data.get('id')
        if not admin_id:
            return jsonify({'message': 'Admin ID is required'}), 400
        
        admin = AdminUser.query.get(admin_id)
        if not admin:
            return jsonify({'message': 'Admin not found'}), 404
        
        # Update fields
        if 'name' in data:
            admin.name = data['name']
        if 'email' in data:
            admin.email = data['email']
        if 'role' in data:
            role = AdminRoleModel.query.filter_by(name=data['role']).first()
            if role:
                admin.role_id = role.id
        if 'password' in data:
            admin.password_hash = generate_password_hash(data['password'])
        if 'is_active' in data:
            admin.is_active = data['is_active']
        
        try:
            db.session.commit()
            return jsonify({'message': 'Admin updated successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500
    
    elif request.method == 'DELETE':
        admin_id = request.args.get('id')
        if not admin_id:
            return jsonify({'message': 'Admin ID is required'}), 400
        
        admin = AdminUser.query.get(admin_id)
        if not admin:
            return jsonify({'message': 'Admin not found'}), 404
        
        try:
            db.session.delete(admin)
            db.session.commit()
            return jsonify({'message': 'Admin deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500

# Companies Management
@admin_bp.route('/companies', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_bp.route('/companies/<int:company_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_bp.route('/companies/export', methods=['GET'])
@require_admin_permission(AdminPermission.VIEW_COMPANIES)
def manage_companies(company_id=None):
    if request.method == 'GET':
        print("DEBUG: Accessing companies endpoint")  # Debug log
        
        if request.path.endswith('/export'):
            # Export companies to CSV
            companies = User.query.all()
            print(f"DEBUG: Found {len(companies)} companies for export")  # Debug log
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Company Name', 'Email', 'Phone', 'Website', 'Business Address',
                'Niche', 'Subscription Plan', 'Status', 'Created At'
            ])
            
            # Write data
            for user in companies:
                writer.writerow([
                    user.company_name or user.user_name,
                    user.user_email,
                    user.company_phone or user.user_phone,
                    user.company_website,
                    user.business_address,
                    user.niche,
                    user.subscription_plan,
                    user.subscription_status,
                    user.created_at.isoformat() if user.created_at else ''
                ])
            
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='companies.csv'
            )
        
        if company_id:
            # Get single company (user)
            user = User.query.get(company_id)
            print(f"DEBUG: Getting company with ID {company_id}: {user}")  # Debug log
            if not user:
                return jsonify({'message': 'Company not found'}), 404
            
            return jsonify({
                'id': user.id,
                'company_name': user.company_name or user.user_name,
                'user_email': user.user_email,
                'company_phone': user.company_phone or user.user_phone,
                'company_website': user.company_website,
                'business_address': user.business_address,
                'niche': user.niche,
                'subscription_plan': user.subscription_plan,
                'subscription_status': user.subscription_status,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        # Get all companies (users)
        users = User.query.all()
        print(f"DEBUG: Found {len(users)} users/companies")  # Debug log
        for user in users:
            print(f"DEBUG: User {user.id}: {user.user_name} - {user.user_email}")  # Debug log
        
        return jsonify({
            "companies": [{
                "id": user.id,
                "company_name": user.company_name or user.user_name,
                "user_email": user.user_email,
                "company_phone": user.company_phone or user.user_phone,
                "company_website": user.company_website or '',
                "business_address": user.business_address or '',
                "niche": user.niche or '',
                "subscription_plan": user.subscription_plan or 'basic',
                "subscription_status": user.subscription_status or 'active',
                "created_at": user.created_at.isoformat() if user.created_at else None
            } for user in users]
        })
    
    elif request.method == 'PUT':
        if not company_id:
            return jsonify({'message': 'Company ID is required'}), 400
        
        user = User.query.get(company_id)
        if not user:
            return jsonify({'message': 'Company not found'}), 404
        
        data = request.get_json()
        
        # Update company fields
        if 'company_name' in data:
            user.company_name = data['company_name']
        if 'user_email' in data:
            user.user_email = data['user_email']
        if 'company_phone' in data:
            user.company_phone = data['company_phone']
        if 'company_website' in data:
            user.company_website = data['company_website']
        if 'business_address' in data:
            user.business_address = data['business_address']
        if 'niche' in data:
            user.niche = data['niche']
        if 'subscription_plan' in data:
            user.subscription_plan = data['subscription_plan']
        if 'subscription_status' in data:
            user.subscription_status = data['subscription_status']
        
        try:
            db.session.commit()
            return jsonify({'message': 'Company updated successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500
    
    elif request.method == 'DELETE':
        if not company_id:
            return jsonify({'message': 'Company ID is required'}), 400
        
        user = User.query.get(company_id)
        if not user:
            return jsonify({'message': 'Company not found'}), 404
        
        try:
            # Delete associated chatbot if exists
            from chatbot.models import ChatbotConfig
            chatbot = ChatbotConfig.query.filter_by(company_id=user.id).first()
            if chatbot:
                db.session.delete(chatbot)
            
            # Delete the user/company
            db.session.delete(user)
            db.session.commit()
            return jsonify({'message': 'Company deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500

# Payments Management
@admin_bp.route('/payments', methods=['GET'])
@require_admin_permission(AdminPermission.VIEW_PAYMENTS)
def get_payments():
    try:
        # Return empty payments list if payments module is not available
        try:
            from payments.models import Payment
            from datetime import datetime, timedelta
            
            last_30_days = datetime.utcnow() - timedelta(days=30)
            payments = Payment.query.filter(
                Payment.created_at >= last_30_days
            ).order_by(Payment.created_at.desc()).all()
            
            return jsonify({
                "payments": [{
                    "id": payment.id,
                    "company": payment.user.company_name if payment.user else 'N/A',
                    "amount": float(payment.amount) / 100,  # Convert cents to dollars
                    "plan": payment.subscription_plan,
                    "status": payment.status,
                    "date": payment.created_at.isoformat() if payment.created_at else None,
                    "payment_method": payment.payment_method,
                    "invoice_url": payment.invoice_url
                } for payment in payments]
            })
        except ImportError:
            logger.warning("Payments module not available")
            return jsonify({"payments": []})
            
    except Exception as e:
        logger.error(f"Error getting payments: {str(e)}", exc_info=True)
        return jsonify({"payments": []})  # Return empty list instead of error

# Get payment details
@admin_bp.route('/payments/<int:payment_id>', methods=['GET'])
@require_admin_permission(AdminPermission.VIEW_PAYMENTS)
def get_payment_details(payment_id):
    try:
        try:
            from payments.models import Payment
            
            payment = Payment.query.get_or_404(payment_id)
            
            return jsonify({
                "id": payment.id,
                "company": payment.user.company_name if payment.user else 'N/A',
                "user_email": payment.user.user_email if payment.user else 'N/A',
                "amount": float(payment.amount) / 100,
                "plan": payment.subscription_plan,
                "status": payment.status,
                "date": payment.created_at.isoformat() if payment.created_at else None,
                "payment_method": payment.payment_method,
                "invoice_url": payment.invoice_url,
                "billing_details": payment.billing_details,
                "metadata": payment.metadata
            })
        except ImportError:
            logger.warning("Payments module not available")
            return jsonify({"error": "Payment system not available"}), 404
            
    except Exception as e:
        logger.error(f"Error getting payment details: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# API Management
@admin_bp.route('/apis', methods=['GET', 'POST', 'DELETE'])
@require_admin_permission(AdminPermission.VIEW_APIS)
def manage_apis():
    if request.method == 'GET':
        # This is a placeholder - you'll need to implement your API key model and logic
        apis = []  # Replace with actual API key query
        return jsonify({
            "apis": [{
                "id": api.id,
                "key": api.key,
                "company": api.company_name,
                "created_at": api.created_at.isoformat() if api.created_at else None,
                "status": api.status
            } for api in apis]
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        company_id = data.get('company_id')
        if not company_id:
            return jsonify({'message': 'Company ID is required'}), 400
        
        # Generate new API key
        api_key = generate_api_key()  # Implement this function
        
        try:
            # Save API key to database
            # api = ApiKey(company_id=company_id, key=api_key)
            # db.session.add(api)
            # db.session.commit()
            return jsonify({'message': 'API key generated successfully', 'key': api_key})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500
    
    elif request.method == 'DELETE':
        api_id = request.args.get('id')
        if not api_id:
            return jsonify({'message': 'API ID is required'}), 400
        
        # api = ApiKey.query.get(api_id)
        # if not api:
        #     return jsonify({'message': 'API key not found'}), 404
        
        try:
            # db.session.delete(api)
            # db.session.commit()
            return jsonify({'message': 'API key deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500

# Support Tickets Management
@admin_bp.route('/support/tickets', methods=['GET', 'POST'])
@login_required
def manage_support_tickets():
    if request.method == 'POST':
        try:
            # Get form data
            form_data = request.form
            files = request.files
            
            # Debug logging
            print("Form data:", form_data)
            print("Files:", files)
            
            # Get company_id from form data
            company_id = form_data.get('company_id')
            print(f"Company ID from form: {company_id}")
            
            if not company_id:
                return jsonify({
                    'error': 'Missing company_id',
                    'details': {'company_id': 'Company ID is required'}
                }), 400
            
            try:
                company_id = int(company_id)
                print(f"Converted company_id to int: {company_id}")
            except ValueError:
                return jsonify({
                    'error': 'Invalid company_id',
                    'details': {'company_id': 'Company ID must be a valid number'}
                }), 400
            
            # Validate required fields
            required_fields = ['subject', 'category', 'priority', 'description']
            missing_fields = [field for field in required_fields if not form_data.get(field)]
            
            if missing_fields:
                return jsonify({
                    'error': 'Missing required fields',
                    'details': {'missing_fields': missing_fields}
                }), 400
            
            # Handle file attachment if present
            attachment_path = None
            if 'attachment' in files and files['attachment'].filename:
                file = files['attachment']
                filename = secure_filename(file.filename)
                attachment_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(attachment_path)
            
            # Create ticket manually setting all fields directly
            ticket = SupportTicket()
            ticket.ticket_number = f"TKT-{os.urandom(4).hex().upper()}"
            ticket.user_id = current_user.id
            ticket.company_id = company_id  # Set company_id directly 
            ticket.subject = form_data.get('subject')
            ticket.category = form_data.get('category')
            ticket.priority = form_data.get('priority')
            ticket.description = form_data.get('description')
            ticket.status = 'open'
            
            print(f"Created ticket object with company_id: {ticket.company_id}")
            
            db.session.add(ticket)
            db.session.commit()
            
            return jsonify({
                'message': 'Ticket created successfully',
                'ticket_number': ticket.ticket_number
            }), 201
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating ticket: {str(e)}")
            return jsonify({
                'error': 'Failed to create ticket',
                'details': str(e)
            }), 500
            
    # GET request handling
    try:
        # For admin users, show all tickets
        if current_user.role and current_user.role.name == 'super_admin':
            tickets = SupportTicket.query.all()
        else:
            # For regular users, show only their company's tickets
            tickets = SupportTicket.query.filter_by(company_id=current_user.company_id).all()
        
        print(f"Found {len(tickets)} tickets")
        
        # Get company IDs directly from the tickets
        ticket_company_ids = [ticket.company_id for ticket in tickets if ticket.company_id is not None]
        print(f"Ticket company_ids: {ticket_company_ids}")
        
        # Look up users by these IDs
        if ticket_company_ids:
            companies = User.query.filter(User.id.in_(ticket_company_ids)).all()
            print(f"Found {len(companies)} companies")
            for company in companies:
                print(f"Company ID: {company.id}, Name: {company.company_name}, User Name: {company.user_name}")
        else:
            companies = []
            print("No company IDs found in tickets")
        
        # Create a mapping of company ID to company name
        company_map = {}
        for company in companies:
            company_name = company.company_name or company.user_name or 'Unknown'
            company_map[company.id] = company_name
            print(f"Mapped company ID {company.id} to name: {company_name}")
        
        print(f"Final company map: {company_map}")
        
        # Create ticket data with proper company names
        ticket_data = []
        for ticket in tickets:
            # Get company name, checking if company_id exists and is in our map
            if ticket.company_id and ticket.company_id in company_map:
                company_name = company_map[ticket.company_id]
            else:
                # If company_id is missing, try to get it from the user
                user = User.query.get(ticket.user_id)
                if user and (user.company_name or user.user_name):
                    company_name = user.company_name or user.user_name
                else:
                    company_name = 'Unknown Company'
                
                print(f"Ticket {ticket.id} has company_id {ticket.company_id}, using name: {company_name}")
            
            ticket_data.append({
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'company': company_name,
                'company_name': company_name,
                'subject': ticket.subject,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'description': ticket.description,
                'created_at': ticket.created_at.isoformat() if ticket.created_at else None
            })
        
        print(f"Generated {len(ticket_data)} ticket data entries")
        
        return jsonify({
            'tickets': ticket_data
        })
    except Exception as e:
        print(f"Error fetching tickets: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch tickets',
            'details': str(e)
        }), 500

@admin_bp.route('/support/tickets/<int:ticket_id>', methods=['GET', 'PUT'])
@login_required
def manage_ticket(ticket_id):
    if request.method == 'PUT':
        try:
            # Update ticket status
            print(f"Updating ticket {ticket_id}")
            ticket = SupportTicket.query.get_or_404(ticket_id)
            
            data = request.get_json()
            print(f"Update data: {data}")
            
            if 'status' in data:
                ticket.status = data['status']
                print(f"Setting ticket status to: {ticket.status}")
            
            db.session.commit()
            
            return jsonify({
                'message': 'Ticket updated successfully',
                'ticket': {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'status': ticket.status
                }
            })
        except Exception as e:
            db.session.rollback()
            print(f"Error updating ticket: {str(e)}")
            return jsonify({
                'error': 'Failed to update ticket',
                'details': str(e)
            }), 500
    
    # GET request - fetch single ticket details
    try:
        ticket = SupportTicket.query.get_or_404(ticket_id)
        print(f"Fetching details for ticket ID: {ticket_id}, company_id: {ticket.company_id}")
        
        # Get company name
        company_name = 'Unknown Company'
        
        # Try to get company from company_id first
        if ticket.company_id:
            company = User.query.get(ticket.company_id)
            if company:
                company_name = company.company_name or company.user_name or 'Unknown Company'
                print(f"Found company by company_id: {company_name}")
        
        # If we couldn't get company from company_id, try from user_id
        if company_name == 'Unknown Company' and ticket.user_id:
            user = User.query.get(ticket.user_id)
            if user:
                company_name = user.company_name or user.user_name or 'Unknown Company'
                print(f"Found company by user_id: {company_name}")
        
        return jsonify({
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'company_name': company_name,
            'subject': ticket.subject,
            'category': ticket.category,
            'priority': ticket.priority,
            'status': ticket.status,
            'description': ticket.description,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None
        })
    except Exception as e:
        print(f"Error fetching ticket details: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch ticket details',
            'details': str(e)
        }), 500

# Super Admin Setup
@admin_bp.route('/setup', methods=['POST'])
def setup_super_admin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400
    
    # Get or create super admin role
    super_admin_role = AdminRoleModel.query.filter_by(name=AdminRole.SUPER_ADMIN.value).first()
    if not super_admin_role:
        super_admin_role = AdminRoleModel(
            name=AdminRole.SUPER_ADMIN.value,
            description="Super Admin role with all permissions",
            permissions=[p.value for p in AdminPermission]
        )
        db.session.add(super_admin_role)
        db.session.commit()
    
    # Check if user with this email already exists
    existing_user = AdminUser.query.filter_by(email=email).first()
    if existing_user:
        # Update existing user to be super admin
        existing_user.role_id = super_admin_role.id
        existing_user.password_hash = generate_password_hash(password)
        existing_user.is_active = True
        db.session.commit()
        return jsonify({'message': 'Existing user updated to super admin successfully'}), 200
    
    # Create new super admin user
    super_admin = AdminUser(
        email=email,
        password_hash=generate_password_hash(password),
        name="Super Admin",
        role_id=super_admin_role.id,
        is_active=True
    )
    
    try:
        db.session.add(super_admin)
        db.session.commit()
        return jsonify({'message': 'Super admin created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 500

# Users Management
@admin_bp.route('/users', methods=['GET'])
@admin_bp.route('/users/<int:user_id>', methods=['GET', 'DELETE'])
@admin_bp.route('/users/export', methods=['GET'])
@require_admin_permission(AdminPermission.VIEW_COMPANIES)  # Reusing companies permission
def manage_users(user_id=None):
    if request.method == 'GET':
        if request.path.endswith('/export'):
            # Export users to CSV
            users = User.query.all()
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Name', 'Email', 'Phone', 'Company Name', 'Subscription Plan', 
                'Status', 'Created At'
            ])
            
            # Write data
            for user in users:
                writer.writerow([
                    user.user_name,
                    user.user_email,
                    user.user_phone,
                    user.company_name,
                    user.subscription_plan,
                    user.subscription_status,
                    user.created_at.isoformat() if user.created_at else ''
                ])
            
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='users.csv'
            )
        
        if user_id:
            # Get single user
            user = User.query.get(user_id)
            if not user:
                return jsonify({'message': 'User not found'}), 404
            
            return jsonify({
                'id': user.id,
                'user_name': user.user_name,
                'user_email': user.user_email,
                'user_phone': user.user_phone,
                'company_name': user.company_name,
                'company_phone': user.company_phone,
                'company_website': user.company_website,
                'business_address': user.business_address,
                'niche': user.niche,
                'subscription_plan': user.subscription_plan,
                'subscription_status': user.subscription_status,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        # Get all users
        users = User.query.all()
        return jsonify({
            "users": [{
                'id': user.id,
                'user_name': user.user_name,
                'user_email': user.user_email,
                'user_phone': user.user_phone,
                'company_name': user.company_name,
                'subscription_plan': user.subscription_plan,
                'subscription_status': user.subscription_status,
                'created_at': user.created_at.isoformat() if user.created_at else None
            } for user in users]
        })
    
    elif request.method == 'DELETE':
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        try:
            # Delete associated chatbot if exists
            from chatbot.models import ChatbotConfig
            chatbot = ChatbotConfig.query.filter_by(company_id=user.id).first()
            if chatbot:
                db.session.delete(chatbot)
            
            # Delete the user
            db.session.delete(user)
            db.session.commit()
            return jsonify({'message': 'User deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500 