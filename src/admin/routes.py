from flask import Blueprint, request, jsonify, send_from_directory, session, redirect, send_file, current_app
from core.database import db
from admin.models import AdminUser, AdminRole, AdminPermission, AdminRoleModel, ApiKey
from admin.decorators import require_admin_role, require_admin_permission
from core.utils import verify_jwt
import os
import json
import csv
import logging
from datetime import datetime, timedelta
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO
from io import StringIO

# Try to import optional modules, use placeholder if not available
try:
    from companies.models import Company, CompanyFeatureSettings
except ImportError:
    logging.warning("Companies module not available")
    Company = None
    CompanyFeatureSettings = None

try:
    from users.models import User
except ImportError:
    logging.warning("Users module not available")
    User = None

try:
    from admin_panel.models import SupportTicket, MessageAttachment
except ImportError:
    logging.warning("Admin panel models not available")
    SupportTicket = None
    MessageAttachment = None

try:
    from chatbot.models import ChatSession
except ImportError:
    logging.warning("ChatSession model not available")
    ChatSession = None

# Remove the Payment import as it doesn't exist
# from payments.models import Payment

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
@admin_bp.route('/admin')
@admin_bp.route('/admin/dashboard')
def serve_dashboard():
    # Check if admin is logged in using Flask-Login
    if not current_user.is_authenticated:
        return redirect('/static/login.html')
    
    if not current_user.is_active:
        return redirect('/static/login.html')
    
    return send_from_directory('static', 'admin.html')

# Dashboard stats
@admin_bp.route('/dashboard/stats')
@login_required
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
        if User is not None:
            stats['totalCompanies'] = db.session.query(db.func.count(User.id)).filter(
                User.company_name.isnot(None)
            ).scalar() or 0
        
        # Get active subscriptions
        if User is not None:
            stats['activeSubscriptions'] = db.session.query(db.func.count(User.id)).filter(
                User.subscription_status == 'active'
            ).scalar() or 0
        
        # Get pending support tickets
        if SupportTicket is not None:
            stats['pendingSupport'] = db.session.query(db.func.count(SupportTicket.id)).filter(
                SupportTicket.status == 'open'
            ).scalar() or 0
        
        # Get API usage
        if ChatSession is not None:
            last_24h = datetime.utcnow() - timedelta(hours=24)
            stats['apiUsage'] = db.session.query(db.func.count(ChatSession.id)).filter(
                ChatSession.created_at >= last_24h
            ).scalar() or 0
        
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
            # Check if User model is available
            if User is None:
                return jsonify({"error": "Users module not available"}), 404
                
            # Export companies to CSV
            companies = User.query.all()
            print(f"DEBUG: Found {len(companies)} companies for export")  # Debug log
            output = StringIO()
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
                BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='companies.csv'
            )
        
        if company_id:
            # Check if User model is available
            if User is None:
                return jsonify({"error": "Users module not available"}), 404
                
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
        
        # Check if User model is available
        if User is None:
            return jsonify({"error": "Users module not available"}), 404
            
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
        
        # Check if User model is available
        if User is None:
            return jsonify({"error": "Users module not available"}), 404
            
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
        
        # Check if User model is available
        if User is None:
            return jsonify({"error": "Users module not available"}), 404
            
        user = User.query.get(company_id)
        if not user:
            return jsonify({'message': 'Company not found'}), 404
        
        try:
            # Try to delete associated chatbot if exists
            try:
                from chatbot.models import ChatbotConfig
                chatbot = ChatbotConfig.query.filter_by(company_id=user.id).first()
                if chatbot:
                    db.session.delete(chatbot)
            except ImportError:
                logger.warning("ChatbotConfig model not available")
            
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
        # Import payment model with multiple import paths
        try:
            from models.subscription import Payment, Subscription
        except ImportError:
            try:
                from src.models.subscription import Payment, Subscription
            except ImportError:
                from backend.src.models.subscription import Payment, Subscription
                
        from users.models import User
        
        # Fetch payments from database with joins to get company info
        payments_query = db.session.query(
            Payment, Subscription, User
        ).join(
            Subscription, Payment.subscription_id == Subscription.id
        ).join(
            User, Subscription.company_id == User.id
        ).all()
        
        # Format payment data for frontend
        payments_data = []
        for payment, subscription, user in payments_query:
            # Format payment data
            payment_data = {
                "id": payment.id,
                "company": user.company_name or user.user_name,
                "user_email": user.user_email,
                "phone": user.company_phone or user.user_phone,
                "website": user.company_website,
                "plan": subscription.plan.value if hasattr(subscription.plan, 'value') else subscription.plan,
                "amount": payment.amount / 100,  # Convert cents to dollars
                "status": payment.status,
                "date": payment.payment_date.isoformat(),
                "payment_method": payment.payment_method
            }
            payments_data.append(payment_data)
            
        logger.info(f"Fetched {len(payments_data)} payment records from database")
        return jsonify({"payments": payments_data})
            
    except ImportError as e:
        logger.warning(f"Payment model import error: {str(e)}")
        return jsonify({"payments": []})
    except Exception as e:
        logger.error(f"Error getting payments: {str(e)}", exc_info=True)
        return jsonify({"payments": []})  # Return empty list instead of error

# Get payment details
@admin_bp.route('/payments/<int:payment_id>', methods=['GET'])
@require_admin_permission(AdminPermission.VIEW_PAYMENTS)
def get_payment_details(payment_id):
    try:
        # Import payment model with multiple import paths
        try:
            from models.subscription import Payment, Subscription
        except ImportError:
            try:
                from src.models.subscription import Payment, Subscription
            except ImportError:
                from backend.src.models.subscription import Payment, Subscription
                
        from users.models import User
        
        # Find the payment record by ID with joins to get subscription and company info
        payment_query = db.session.query(
            Payment, Subscription, User
        ).join(
            Subscription, Payment.subscription_id == Subscription.id
        ).join(
            User, Subscription.company_id == User.id
        ).filter(
            Payment.id == payment_id
        ).first()
        
        if not payment_query:
            return jsonify({"error": f"Payment not found with ID: {payment_id}"}), 404
            
        payment, subscription, user = payment_query
        
        # Format payment data with subscription and user details
        payment_data = {
            "id": payment.id,
            "company": user.company_name or user.user_name,
            "user_email": user.user_email,
            "phone": user.company_phone or user.user_phone,
            "website": user.company_website,
            "plan": subscription.plan.value if hasattr(subscription.plan, 'value') else subscription.plan,
            "amount": payment.amount / 100,  # Convert cents to dollars
            "status": payment.status,
            "date": payment.payment_date.isoformat(),
            "payment_method": payment.payment_method,
            "transaction_id": payment.transaction_id,
            "currency": payment.currency
        }
        
        # Add any metadata if available
        if payment.metadata:
            payment_data.update(payment.metadata)
        
        return jsonify(payment_data)
            
    except ImportError as e:
        logger.warning(f"Payment model import error: {str(e)}")
        return jsonify({"error": "Payment system not available"}), 404
    except Exception as e:
        logger.error(f"Error getting payment details: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# API Management
@admin_bp.route('/direct-api-key', methods=['POST'])
@require_admin_permission(AdminPermission.VIEW_APIS)
def direct_api_key():
    """
    Direct endpoint for inserting an API key into the database.
    This is used by the admin dashboard to generate API keys that can be retrieved by the user dashboard.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting direct API key insertion process")
    
    try:
        data = request.get_json()
        logger.info(f"Received data: {data}")
        
        company_id = data.get('company_id')
        api_key = data.get('api_key')
        
        if not company_id:
            logger.error("Company ID is required but was not provided")
            return jsonify({'error': 'Company ID is required'}), 400
            
        if not api_key:
            logger.error("API key is required but was not provided")
            return jsonify({'error': 'API key is required'}), 400
        
        logger.info(f"Inserting API key for company ID: {company_id}")
        
        # Check if Company model is available
        if Company is None:
            logger.error("Companies module not available")
            return jsonify({'error': 'Companies module not available'}), 500
            
        # Get company to verify it exists and get subscription plan
        company = Company.query.get(company_id)
        if not company:
            logger.error(f"Company with ID {company_id} not found")
            return jsonify({'error': 'Company not found'}), 404
        
        logger.info(f"Found company: {company.name} with plan: {company.subscription_plan}")
        
        # Use raw SQL to insert the API key
        from sqlalchemy import text
        
        # Create insert SQL that works with both schema versions
        try:
            # First try with the status column
            insert_sql = text("""
                INSERT INTO api_keys (key, company_id, subscription_plan, status, created_at)
                VALUES (:key, :company_id, :subscription_plan, :status, NOW())
                RETURNING id
            """)
            
            # Execute the insert
            result = db.session.execute(
                insert_sql, 
                {
                    "key": api_key,
                    "company_id": company_id,
                    "subscription_plan": company.subscription_plan,
                    "status": "active"
                }
            )
            
            # Get the ID of the newly inserted API key
            new_id = result.fetchone()[0]
            logger.info(f"Inserted new API key with ID: {new_id} using status column")
        except Exception as e:
            logger.warning(f"Error inserting API key with status column: {str(e)}. Trying with active column...")
            
            # Try with the active column instead
            try:
                insert_sql_alt = text("""
                    INSERT INTO api_keys (key, company_id, active, created_at)
                    VALUES (:key, :company_id, :active, NOW())
                    RETURNING id
                """)
                
                # Execute the insert
                result = db.session.execute(
                    insert_sql_alt, 
                    {
                        "key": api_key,
                        "company_id": company_id,
                        "active": True
                    }
                )
                
                # Get the ID of the newly inserted API key
                new_id = result.fetchone()[0]
                logger.info(f"Inserted new API key with ID: {new_id} using active column")
            except Exception as inner_e:
                logger.error(f"Error inserting API key with active column: {str(inner_e)}")
                raise inner_e
        
        # Commit the transaction
        db.session.commit()
        logger.info("API key insertion successful, transaction committed")
        
        return jsonify({
            'success': True,
            'message': 'API key inserted successfully', 
            'key': api_key,
            'company': company.name,
            'subscription_plan': company.subscription_plan
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error inserting API key: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/apis', methods=['GET', 'POST', 'DELETE'])
@require_admin_permission(AdminPermission.VIEW_APIS)
def manage_apis():
    if request.method == 'GET':
        try:
            # Use raw SQL to get all API keys to avoid ORM issues with missing columns
            from sqlalchemy import text
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Join with companies table to get company names
            sql = text("""
                SELECT a.id, a.key, a.company_id, a.subscription_plan, a.status, a.created_at, c.name as company_name, c.subscription_plan as company_plan
                FROM api_keys a
                LEFT JOIN companies c ON a.company_id = c.id
                ORDER BY a.created_at DESC
            """)
            
            result = db.session.execute(sql)
            apis_data = []
            
            for row in result:
                # Convert row to dict
                api_dict = {
                    "id": row.id,
                    "key": row.key,
                    "company_id": row.company_id,
                    "company": row.company_name or "Unknown",
                    "subscription_plan": row.subscription_plan or row.company_plan or 'basic',
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "status": row.status or 'active'
                }
                apis_data.append(api_dict)
            
            return jsonify({"apis": apis_data})
        except Exception as e:
            logger.error(f"Error getting API keys: {str(e)}", exc_info=True)
            return jsonify({"error": str(e), "apis": []}), 500
    
    elif request.method == 'POST':
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Starting API key generation process")
        
        try:
            data = request.get_json()
            logger.info(f"Received data: {data}")
            
            company_id = data.get('company_id')
            if not company_id:
                logger.error("Company ID is required but was not provided")
                return jsonify({'error': 'Company ID is required'}), 400
            
            logger.info(f"Generating API key for company ID: {company_id}")
            
            # Check if Company model is available
            if Company is None:
                logger.error("Companies module not available")
                return jsonify({'error': 'Companies module not available'}), 500
                
            # Get company to verify it exists and get subscription plan
            company = Company.query.get(company_id)
            if not company:
                logger.error(f"Company with ID {company_id} not found")
                return jsonify({'error': 'Company not found'}), 404
            
            logger.info(f"Found company: {company.name} with plan: {company.subscription_plan}")
            
            # Generate new API key
            api_key = generate_api_key()
            logger.info(f"Generated new API key: {api_key[:8]}...")
            
            # Use raw SQL to insert the API key
            from sqlalchemy import text
            
            # Create insert SQL
            insert_sql = text("""
                INSERT INTO api_keys (key, company_id, subscription_plan, status, created_at)
                VALUES (:key, :company_id, :subscription_plan, :status, NOW())
                RETURNING id
            """)
            
            # Execute the insert
            result = db.session.execute(
                insert_sql, 
                {
                    "key": api_key,
                    "company_id": company_id,
                    "subscription_plan": company.subscription_plan,
                    "status": "active"
                }
            )
            
            # Get the ID of the newly inserted API key
            new_id = result.fetchone()[0]
            logger.info(f"Inserted new API key with ID: {new_id}")
            
            # Commit the transaction
            db.session.commit()
            logger.info("API key generation successful, transaction committed")
            
            return jsonify({
                'message': 'API key generated successfully', 
                'key': api_key,
                'company': company.name,
                'subscription_plan': company.subscription_plan
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error generating API key: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        api_id = request.args.get('id')
        if not api_id:
            return jsonify({'error': 'API ID is required'}), 400
        
        try:
            from sqlalchemy import text
            import logging
            
            logger = logging.getLogger(__name__)
            
            # First check if the API key exists
            check_sql = text("SELECT id FROM api_keys WHERE id = :id LIMIT 1")
            result = db.session.execute(check_sql, {"id": api_id})
            api = result.fetchone()
            
            if not api:
                return jsonify({'error': 'API key not found'}), 404
            
            # Delete the API key using raw SQL
            delete_sql = text("DELETE FROM api_keys WHERE id = :id")
            db.session.execute(delete_sql, {"id": api_id})
            db.session.commit()
            
            return jsonify({'message': 'API key deleted successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting API key: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

@admin_bp.route('/companies/list', methods=['GET'])
@require_admin_permission(AdminPermission.VIEW_COMPANIES)
def get_companies_list():
    """Get a simple list of companies for dropdowns"""
    # Check if User model is available
    if User is None:
        return jsonify({'error': 'Users module not available'}), 500
        
    # Use User model instead of Company model to be consistent
    users = User.query.all()
    return jsonify({
        "companies": [{
            "id": user.id,
            "name": user.company_name or user.user_name,
            "subscription_plan": user.subscription_plan or 'basic'
        } for user in users]
    })

def generate_api_key():
    """Generate a unique API key"""
    import secrets
    import string
    from sqlalchemy import text
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Generate a random string of 48 characters
    alphabet = string.ascii_letters + string.digits
    while True:
        # Create API key with a prefix for easy identification
        api_key = 'sk_' + ''.join(secrets.choice(alphabet) for _ in range(48))
        
        try:
            # Use raw SQL to check if key exists to avoid ORM issues with missing columns
            sql = text("SELECT id FROM api_keys WHERE key = :key LIMIT 1")
            result = db.session.execute(sql, {"key": api_key})
            existing = result.fetchone()
            
            if not existing:
                return api_key
        except Exception as e:
            logger.error(f"Error checking for existing API key: {str(e)}")
            # Generate a new key if there was an error
            continue

# Support Tickets Management
@admin_bp.route('/support/tickets', methods=['GET', 'POST'])
@login_required
def manage_support_tickets():
    # Check if SupportTicket model is available
    if SupportTicket is None:
        return jsonify({"error": "Support ticket module not available"}), 500
    
    # GET method: List all tickets
    if request.method == 'GET':
        try:
            # For support role, we'll only show tickets they're assigned to or open tickets
            if current_user.role and current_user.role.name == 'support':
                tickets = SupportTicket.query.filter(
                    (SupportTicket.assigned_to == current_user.id) | 
                    (SupportTicket.status == 'open')
                ).all()
            # Super admin sees all tickets
            else:
                tickets = SupportTicket.query.all()
            
            # Format ticket data with company names
            ticket_data = []
            for ticket in tickets:
                # Get company name from company_id
                company_name = 'Unknown Company'
                
                # Try to get company from company_id
                if hasattr(ticket, 'company_id') and ticket.company_id:
                    try:
                        # Try to get company from Company model
                        if Company is not None:
                            company = Company.query.get(ticket.company_id)
                            if company:
                                company_name = company.name
                        
                        # If that fails, try to get from User model
                        if company_name == 'Unknown Company' and User is not None:
                            user = User.query.get(ticket.company_id)
                            if user:
                                company_name = user.company_name or user.user_name or 'Unknown Company'
                    except Exception as e:
                        logger.error(f"Error getting company name: {str(e)}")
                
                # Format the ticket data
                ticket_dict = {
                    "id": ticket.id,
                    "ticket_number": getattr(ticket, 'ticket_number', f'TKT-{ticket.id}'),
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                    "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                    "company_name": company_name,
                    "company": company_name,  # Duplicate for compatibility with frontend
                    "topic": getattr(ticket, 'topic', ''),
                    "details": getattr(ticket, 'details', '') or getattr(ticket, 'description', '') or '',
                    "description": getattr(ticket, 'description', '') or getattr(ticket, 'details', '') or '',
                    "assigned_to": getattr(ticket, 'assigned_to', None),
                    "remarks": getattr(ticket, 'remarks', '')
                }
                ticket_data.append(ticket_dict)
            
            return jsonify({
                "tickets": ticket_data
            })
        except Exception as e:
            logger.error(f"Error getting support tickets: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to get support tickets: {str(e)}"}), 500
    
    # POST method: Create a new ticket
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
            try:
                ticket.ticket_number = f"TKT-{os.urandom(4).hex().upper()}"
            except Exception as e:
                logger.error(f"Error setting ticket_number: {str(e)}")
                # If ticket_number attribute doesn't exist yet, it's okay
                pass
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
                'ticket_id': ticket.id
            }), 201
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating ticket: {str(e)}")
            return jsonify({
                'error': 'Failed to create ticket',
                'details': str(e)
            }), 500

# New endpoint for support team to see ALL tickets
@admin_bp.route('/support/tickets/all', methods=['GET'])
@login_required
def get_all_support_tickets():
    # Check if SupportTicket model is available
    if SupportTicket is None:
        return jsonify({"error": "Support ticket module not available"}), 500
    
    try:
        # This endpoint will show ALL tickets, regardless of role
        # But we still check that the user has either support role or is admin
        if current_user.role and (current_user.role.name == 'support' or 
                                 current_user.role.name == 'admin' or 
                                 current_user.role.name == 'super_admin'):
            tickets = SupportTicket.query.all()
            
            # Format ticket data with company names
            ticket_data = []
            for ticket in tickets:
                # Get company name from company_id
                company_name = 'Unknown Company'
                
                # Try to get company from company_id
                if hasattr(ticket, 'company_id') and ticket.company_id:
                    try:
                        # Try to get company from Company model
                        if Company is not None:
                            company = Company.query.get(ticket.company_id)
                            if company:
                                company_name = company.name
                        
                        # If that fails, try to get from User model
                        if company_name == 'Unknown Company' and User is not None:
                            user = User.query.get(ticket.company_id)
                            if user:
                                company_name = user.company_name or user.user_name or 'Unknown Company'
                    except Exception as e:
                        logger.error(f"Error getting company name: {str(e)}")
                
                # Format the ticket data
                ticket_dict = {
                    "id": ticket.id,
                    "ticket_number": getattr(ticket, 'ticket_number', f'TKT-{ticket.id}'),
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                    "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                    "company_name": company_name,
                    "company": company_name,  # Duplicate for compatibility with frontend
                    "topic": getattr(ticket, 'topic', ''),
                    "details": getattr(ticket, 'details', '') or getattr(ticket, 'description', '') or '',
                    "description": getattr(ticket, 'description', '') or getattr(ticket, 'details', '') or '',
                    "assigned_to": getattr(ticket, 'assigned_to', None),
                    "remarks": getattr(ticket, 'remarks', '')
                }
                ticket_data.append(ticket_dict)
            
            return jsonify({
                "tickets": ticket_data
            })
        else:
            return jsonify({"error": "Unauthorized access"}), 403
    except Exception as e:
        logger.error(f"Error getting all support tickets: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get all support tickets: {str(e)}"}), 500

# New endpoint to get ticket counts
@admin_bp.route('/support/tickets/count', methods=['GET'])
@login_required
def get_ticket_counts():
    # Check if SupportTicket model is available
    if SupportTicket is None:
        return jsonify({"error": "Support ticket module not available"}), 500
    
    try:
        # Get total count
        total_count = SupportTicket.query.count()
        
        # Get open ticket count - safely handle status attribute
        try:
            open_count = SupportTicket.query.filter(SupportTicket.status == 'open').count()
        except (AttributeError, Exception) as e:
            logger.error(f"Error querying open tickets: {str(e)}")
            open_count = 0
        
        # Get assigned count (for current user if support role)
        try:
            if current_user.role and current_user.role.name == 'support':
                # Check if assigned_to column exists
                if hasattr(SupportTicket, 'assigned_to'):
                    assigned_count = SupportTicket.query.filter(SupportTicket.assigned_to == current_user.id).count()
                else:
                    assigned_count = 0
            else:
                if hasattr(SupportTicket, 'assigned_to'):
                    assigned_count = SupportTicket.query.filter(SupportTicket.assigned_to.isnot(None)).count()
                else:
                    assigned_count = 0
        except (AttributeError, Exception) as e:
            logger.error(f"Error querying assigned tickets: {str(e)}")
            assigned_count = 0
        
        return jsonify({
            "total": total_count,
            "open": open_count,
            "assigned": assigned_count
        })
    except Exception as e:
        logger.error(f"Error getting ticket counts: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get ticket counts: {str(e)}"}), 500

@admin_bp.route('/support/tickets/<int:ticket_id>', methods=['GET', 'PUT'])
@login_required
def manage_ticket(ticket_id):
    # Check if SupportTicket model is available
    if SupportTicket is None:
        return jsonify({'error': 'Support ticket module not available'}), 404
        
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
            if 'remarks' in data:
                ticket.remarks = data['remarks']
                print(f"Setting ticket remarks to: {ticket.remarks}")
            
            db.session.commit()
            
            response_data = {
                'message': 'Ticket updated successfully',
                'ticket': {
                    'id': ticket.id,
                    'status': ticket.status
                }
            }
            
            # Add ticket_number and remarks to response
            try:
                response_data['ticket']['ticket_number'] = ticket.ticket_number
            except (AttributeError, Exception) as e:
                logger.error(f"Error accessing ticket_number: {str(e)}")
                response_data['ticket']['ticket_number'] = f"TICKET-{ticket.id}"
            # Always include remarks in response
            response_data['ticket']['remarks'] = ticket.remarks
            
            return jsonify(response_data)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating ticket: {str(e)}")
            return jsonify({
                'error': 'Failed to update ticket',
                'details': str(e)
            }), 500
    
    # GET request - fetch single ticket details
    try:
        ticket = SupportTicket.query.get_or_404(ticket_id)
        print(f"Fetching details for ticket ID: {ticket_id}, company_id: {getattr(ticket, 'company_id', None)}")
        
        # Get company name - default to Unknown Company
        company_name = 'Unknown Company'
        
        # Try to get company from company_id if it exists
        if hasattr(ticket, 'company_id') and ticket.company_id:
            # Try to get company from Company model first
            if Company is not None:
                company = Company.query.get(ticket.company_id)
                if company:
                    company_name = company.name or 'Unknown Company'
            
            # If that fails, try to get from User model
            if company_name == 'Unknown Company' and User is not None:
                user = User.query.get(ticket.company_id)
                if user:
                    company_name = user.company_name or user.user_name or 'Unknown Company'
        
        # Always expose the user-entered details
        detail_text = getattr(ticket, 'details', '') or getattr(ticket, 'description', '') or 'No description provided'
        
        ticket_details = {
            'id': ticket.id,
            'company': company_name,
            'company_name': company_name,
            'subject': ticket.subject,
            'category': getattr(ticket, 'category', 'General'),
            'priority': getattr(ticket, 'priority', 'Normal'),
            'status': ticket.status,
            'details': detail_text,
            'description': detail_text,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            'remarks': getattr(ticket, 'remarks', ''),
            'topic': getattr(ticket, 'topic', 'General')
        }
        
        # Add ticket_number if it exists
        try:
            ticket_details['ticket_number'] = ticket.ticket_number
        except (AttributeError, Exception) as e:
            ticket_details['ticket_number'] = f"TICKET-{ticket.id}"
        
        return jsonify(ticket_details)
    except Exception as e:
        logger.error(f"Error fetching ticket details: {str(e)}")
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
@admin_bp.route('/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_bp.route('/users/export', methods=['GET'])
@require_admin_permission(AdminPermission.VIEW_COMPANIES)  # Reusing companies permission
def manage_users(user_id=None):
    # Check if User model is available
    if User is None:
        return jsonify({"error": "Users module not available"}), 404
        
    if request.method == 'GET':
        if request.path.endswith('/export'):
            # Export users to CSV
            users = User.query.all()
            output = StringIO()
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
                BytesIO(output.getvalue().encode('utf-8')),
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
    
    elif request.method == 'PUT':
        if not user_id:
            return jsonify({'message': 'User ID is required'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update user fields
        if 'user_name' in data:
            user.user_name = data['user_name']
        if 'user_email' in data:
            user.user_email = data['user_email']
        if 'user_phone' in data:
            user.user_phone = data['user_phone']
        if 'company_name' in data:
            user.company_name = data['company_name']
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
            return jsonify({'message': 'User updated successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500
    
    elif request.method == 'DELETE':
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        try:
            # Try to delete associated chatbot if exists
            try:
                from chatbot.models import ChatbotConfig
                chatbot = ChatbotConfig.query.filter_by(company_id=user.id).first()
                if chatbot:
                    db.session.delete(chatbot)
            except ImportError:
                logger.warning("ChatbotConfig model not available")
            
            # Delete the user
            db.session.delete(user)
            db.session.commit()
            return jsonify({'message': 'User deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 500

@admin_bp.route('/companies/<int:company_id>/features', methods=['GET', 'PUT'])
@login_required
@require_admin_role(AdminRole.SUPER_ADMIN)
def manage_company_features(company_id):
    try:
        # Check if required models are available
        if User is None:
            return jsonify({'error': 'Users module not available'}), 404
        if Company is None:
            return jsonify({'error': 'Companies module not available'}), 404
        if CompanyFeatureSettings is None:
            return jsonify({'error': 'CompanyFeatureSettings model not available'}), 404
            
        # Use User model instead of Company model
        user = User.query.get(company_id)
        if not user:
            return jsonify({'error': f'Company with ID {company_id} not found'}), 404
        
        if request.method == 'GET':
            # First ensure there's an entry in the companies table to satisfy the foreign key constraint
            company = Company.query.get(company_id)
            if not company:
                # Create a company entry based on the User data
                company = Company(
                    id=user.id,
                    name=user.company_name or user.user_name,
                    email=user.user_email,
                    phone=user.company_phone or user.user_phone,
                    website=user.company_website,
                    business_address=user.business_address,
                    niche=user.niche,
                    subscription_plan=user.subscription_plan or 'basic',
                    status=user.subscription_status or 'active'
                )
                db.session.add(company)
                db.session.commit()
                logger.info(f"Created company entry for ID {company_id}")
                
            # Get or create feature settings
            settings = CompanyFeatureSettings.query.filter_by(company_id=company_id).first()
            if not settings:
                # Create default feature settings if none exist
                settings = CompanyFeatureSettings(
                    company_id=company_id,
                    enabled_features={
                        'chatbot': True,
                        'knowledge_base': True,
                        'support_tickets': True,
                        'api_access': False,
                        'custom_branding': False,
                        'analytics': False,
                        'multi_language': False,
                        'advanced_ai': False,
                        'priority_support': False,
                        'custom_integrations': False
                    },
                    feature_limits={
                        'knowledge_base_documents': 50,
                        'support_tickets_per_month': 10,
                        'api_calls_per_month': 0,
                        'languages': 1
                    }
                )
                db.session.add(settings)
                db.session.commit()
            
            # Ensure enabled_features and feature_limits are dictionaries
            enabled_features = settings.enabled_features or {}
            feature_limits = settings.feature_limits or {}
            
            return jsonify({
                'enabled_features': enabled_features,
                'feature_limits': feature_limits,
                'subscription_plan': user.subscription_plan or 'basic'
            })
        
        elif request.method == 'PUT':
            data = request.get_json()
            
            # Validate feature settings
            if 'enabled_features' not in data or 'feature_limits' not in data:
                return jsonify({'error': 'Missing required fields'}), 400
            
            # First ensure there's an entry in the companies table
            company = Company.query.get(company_id)
            if not company:
                # Create a company entry based on the User data
                company = Company(
                    id=user.id,
                    name=user.company_name or user.user_name,
                    email=user.user_email,
                    phone=user.company_phone or user.user_phone,
                    website=user.company_website,
                    business_address=user.business_address,
                    niche=user.niche,
                    subscription_plan=user.subscription_plan or 'basic',
                    status=user.subscription_status or 'active'
                )
                db.session.add(company)
                db.session.commit()
                logger.info(f"Created company entry for ID {company_id}")
            
            settings = CompanyFeatureSettings.query.filter_by(company_id=company_id).first()
            if not settings:
                settings = CompanyFeatureSettings(company_id=company_id)
                db.session.add(settings)
            
            # Update settings
            settings.enabled_features = data['enabled_features']
            settings.feature_limits = data['feature_limits']
            
            try:
                db.session.commit()
                return jsonify({'message': 'Feature settings updated successfully'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating feature settings: {str(e)}", exc_info=True)
                return jsonify({'error': str(e)}), 500
                
    except Exception as e:
        logger.error(f"Error managing company features: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/companies/<int:company_id>/features/reset', methods=['POST'])
@login_required
@require_admin_role(AdminRole.SUPER_ADMIN)
def reset_company_features(company_id):
    try:
        # Check if required models are available
        if User is None:
            return jsonify({'error': 'Users module not available'}), 404
        if Company is None:
            return jsonify({'error': 'Companies module not available'}), 404
        if CompanyFeatureSettings is None:
            return jsonify({'error': 'CompanyFeatureSettings model not available'}), 404
            
        # Use User model instead of Company model
        user = User.query.get(company_id)
        if not user:
            return jsonify({'error': f'Company with ID {company_id} not found'}), 404
        
        # First ensure there's an entry in the companies table
        company = Company.query.get(company_id)
        if not company:
            # Create a company entry based on the User data
            company = Company(
                id=user.id,
                name=user.company_name or user.user_name,
                email=user.user_email,
                phone=user.company_phone or user.user_phone,
                website=user.company_website,
                business_address=user.business_address,
                niche=user.niche,
                subscription_plan=user.subscription_plan or 'basic',
                status=user.subscription_status or 'active'
            )
            db.session.add(company)
            db.session.commit()
            logger.info(f"Created company entry for ID {company_id}")
            
        # Get plan defaults
        plan_defaults = {
            'basic': {
                'enabled_features': {
                    'chatbot': True,
                    'knowledge_base': True,
                    'support_tickets': True,
                    'api_access': False,
                    'custom_branding': False,
                    'analytics': False,
                    'multi_language': False,
                    'advanced_ai': False,
                    'priority_support': False,
                    'custom_integrations': False
                },
                'feature_limits': {
                    'knowledge_base_documents': 50,
                    'support_tickets_per_month': 10,
                    'api_calls_per_month': 0,
                    'languages': 1
                }
            },
            'pro': {
                'enabled_features': {
                    'chatbot': True,
                    'knowledge_base': True,
                    'support_tickets': True,
                    'api_access': True,
                    'custom_branding': True,
                    'analytics': True,
                    'multi_language': True,
                    'advanced_ai': False,
                    'priority_support': False,
                    'custom_integrations': False
                },
                'feature_limits': {
                    'knowledge_base_documents': 200,
                    'support_tickets_per_month': 50,
                    'api_calls_per_month': 1000,
                    'languages': 3
                }
            },
            'enterprise': {
                'enabled_features': {
                    'chatbot': True,
                    'knowledge_base': True,
                    'support_tickets': True,
                    'api_access': True,
                    'custom_branding': True,
                    'analytics': True,
                    'multi_language': True,
                    'advanced_ai': True,
                    'priority_support': True,
                    'custom_integrations': True
                },
                'feature_limits': {
                    'knowledge_base_documents': float('inf'),
                    'support_tickets_per_month': float('inf'),
                    'api_calls_per_month': float('inf'),
                    'languages': float('inf')
                }
            }
        }
        
        # Get subscription plan safely, defaulting to 'basic'
        subscription_plan = user.subscription_plan or 'basic'
        
        # Get settings for the company's plan
        defaults = plan_defaults.get(subscription_plan, plan_defaults['basic'])
        
        # Update or create settings
        settings = CompanyFeatureSettings.query.filter_by(company_id=company_id).first()
        if not settings:
            settings = CompanyFeatureSettings(company_id=company_id)
            db.session.add(settings)
        
        settings.enabled_features = defaults['enabled_features']
        settings.feature_limits = defaults['feature_limits']
        
        try:
            db.session.commit()
            return jsonify({'message': 'Features reset to plan defaults successfully'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error resetting feature settings: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        logger.error(f"Error resetting company features: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# Create test payment data for demonstration
@admin_bp.route('/payments/seed', methods=['POST'])
@require_admin_role(AdminRole.SUPER_ADMIN)
def seed_payment_data():
    try:
        # Import required models - Fix import path
        try:
            from models.subscription import Payment, Subscription, SubscriptionPlan
        except ImportError:
            # Try alternate import paths
            try:
                from src.models.subscription import Payment, Subscription, SubscriptionPlan
            except ImportError:
                from backend.src.models.subscription import Payment, Subscription, SubscriptionPlan
                
        from users.models import User
        from datetime import datetime, timedelta
        import random
        
        # Check if we already have payment data
        payment_count = db.session.query(Payment).count()
        if payment_count > 0:
            return jsonify({"message": f"Database already has {payment_count} payment records"}), 200
        
        # Get all users that could be companies
        users = User.query.all()
        if not users:
            return jsonify({"error": "No users found to create payment data for"}), 404
        
        payment_methods = ["credit_card", "paypal", "bank_transfer"]
        payment_statuses = ["succeeded", "pending", "failed"]
        currencies = ["USD"]
        
        # Plan amounts in cents
        plan_amounts = {
            "basic": 3900,  # $39
            "pro": 8900,    # $89
            "enterprise": 19900  # $199
        }
        
        payments_created = 0
        
        # Create subscription and payment records for each user
        for user in users:
            # Determine plan - use existing or random
            plan = user.subscription_plan or random.choice(["basic", "pro", "enterprise"])
            
            # Create subscription if doesn't exist
            subscription = db.session.query(Subscription).filter_by(company_id=user.id).first()
            if not subscription:
                subscription = Subscription(
                    company_id=user.id,
                    plan=plan,
                    status="active",
                    start_date=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                    billing_cycle="monthly"
                )
                db.session.add(subscription)
                db.session.flush()  # Get subscription ID
            
            # Create 1-3 payments for this subscription
            for i in range(random.randint(1, 3)):
                payment_date = datetime.utcnow() - timedelta(days=i*30)
                payment = Payment(
                    subscription_id=subscription.id,
                    amount=plan_amounts.get(plan, 3900),
                    currency=random.choice(currencies),
                    status=random.choice(payment_statuses) if i > 0 else "succeeded",  # Most recent is always succeeded
                    payment_method=random.choice(payment_methods),
                    payment_date=payment_date,
                    transaction_id=f"tx_{random.randint(10000, 99999)}_{i}",
                    metadata={
                        "invoice_number": f"INV-{random.randint(1000, 9999)}-{i}",
                        "billing_address": f"{random.randint(100, 999)} Main St, City, Country"
                    }
                )
                db.session.add(payment)
                payments_created += 1
        
        db.session.commit()
        return jsonify({"message": f"Successfully created {payments_created} test payment records"}), 201
        
    except ImportError as e:
        logger.warning(f"Failed to import required models: {str(e)}")
        return jsonify({"error": "Payment models not available"}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating test payment data: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500 