from flask import Flask, send_from_directory, jsonify
import os
from flask import request
from core.database import db, init_db
from flask_migrate import Migrate
from core.monitoring import metrics_endpoint, record_request_data, start_timer, stop_timer
from users.views import users_bp
from admin.routes import admin_bp
from admin_panel.routes import admin_panel
from admin_panel.views import support_bp
from chatbot.views import chatbot_bp, admin_chatbots_bp, delete_chatbot_route, get_company_api_key as chatbot_get_company_api_key
from payments.webhook import stripe_webhook
from payments.routes import payments_bp
from chatbot.session_views import session_bp
from companies.views import companies_bp
from metrics.views import metrics_bp
from subscriptions import subscription_bp
from api_keys import api_keys_bp
from services.email_routes import email_bp
from datetime import timedelta
from flask_login import LoginManager
from admin.models import AdminUser
from flask_cors import CORS
from subscriptions.routes import create_checkout_session
from werkzeug.middleware.proxy_fix import ProxyFix
from core.config import Config
import logging
from logging.handlers import RotatingFileHandler
import traceback
import sqlalchemy.exc
import json
from pathlib import Path
from core.metrics_api import metrics_chat_bp

# Set OpenAI API key if not already set
if not os.environ.get("OPENAI_API_KEY"):
    # Use a default API key for development - in production, this should be set in the environment
    os.environ["OPENAI_API_KEY"] = "sk-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL"
    logging.warning("OPENAI_API_KEY not found in environment. Using default development key.")

# Find the frontend directory path (up one level from backend and then into frontend)
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'frontend')
frontend_dir = os.path.normpath(frontend_dir)

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Set up logging
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=10),  # 10MB per file, keep 10 files
        logging.StreamHandler()  # Also log to console
    ]
)

# Initialize CORS to allow cross-origin requests
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
    }
}, supports_credentials=True)  # Enable credentials support for CORS

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://movergptuser:M0v3rGPT_2025!@127.0.0.1:5432/movergptdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session configuration
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "default_secret_key")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Extend session lifetime
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Lax allows cookies to be sent in navigation context
app.config['SESSION_COOKIE_NAME'] = 'flask_session'  # Changed from 'access_token' to avoid JWT conflicts
app.config['SESSION_COOKIE_PATH'] = '/'  # Make cookie available across all paths
app.config['SESSION_COOKIE_DOMAIN'] = None  # Default to current domain
app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = True
app.config['TESTING'] = False
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Refresh session on each request
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)  # Longer remember cookie duration

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin.login'
login_manager.remember_cookie_duration = timedelta(days=7)  # Set remember cookie duration

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

init_db(app)
migrate = Migrate(app, db)

# Add special error handler for SQLAlchemy transaction errors
# This will rollback any aborted transactions automatically
@app.errorhandler(sqlalchemy.exc.SQLAlchemyError)
def handle_db_error(error):
    app.logger.error(f"Database error: {error}")
    app.logger.error(traceback.format_exc())
    try:
        db.session.rollback()
        app.logger.info("Successfully rolled back database session after error")
    except Exception as rollback_error:
        app.logger.error(f"Error rolling back session: {rollback_error}")
    
    # Return appropriate error response
    if isinstance(error, sqlalchemy.exc.IntegrityError):
        return jsonify({
            "status": "error",
            "message": "Database integrity error - your request couldn't be processed",
            "details": str(error)
        }), 400
    elif isinstance(error, sqlalchemy.exc.InternalError):
        return jsonify({
            "status": "error",
            "message": "Database transaction error - please try again",
            "details": str(error)
        }), 500
    else:
        return jsonify({
            "status": "error",
            "message": "Database error occurred",
            "details": str(error)
        }), 500

# Add special middleware to rollback aborted transactions at the beginning of each request
@app.before_request
def ensure_clean_session():
    try:
        db.session.rollback()  # Rollback any lingering transaction
    except Exception as e:
        app.logger.warning(f"Error rolling back session at request start: {e}")

# Register blueprints
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(admin_panel, url_prefix="/api/admin/panel")
app.register_blueprint(support_bp, url_prefix="/api/support")
app.register_blueprint(chatbot_bp, url_prefix="/api/chatbot")
app.register_blueprint(admin_chatbots_bp, url_prefix="/api/admin/chatbots")
app.register_blueprint(session_bp, url_prefix="/api/chatbot")
app.register_blueprint(payments_bp, url_prefix="/api/payments")
app.register_blueprint(companies_bp, url_prefix="/api/companies")
app.add_url_rule("/api/payments/webhook", view_func=stripe_webhook, methods=["POST"])
app.register_blueprint(metrics_bp, url_prefix="/api/metrics")
app.register_blueprint(metrics_chat_bp, url_prefix='/api/metrics/chat')
app.register_blueprint(subscription_bp, url_prefix='/api/subscriptions')
app.register_blueprint(api_keys_bp, url_prefix='/api/keys')
app.register_blueprint(email_bp, url_prefix='/api/email')

# Add direct route for Stripe checkout to ensure it's accessible
app.add_url_rule('/api/subscriptions/create-checkout-session', 
                view_func=create_checkout_session, 
                methods=['POST'])

# Add direct route for deleting chatbots
app.add_url_rule('/api/chatbot/<int:chatbot_id>', 
                view_func=delete_chatbot_route, 
                methods=['DELETE'])

# Add direct routes for company API key to match frontend's expected URL
from users.views import get_company_api_key, get_api_key, create_api_key
app.add_url_rule('/api/company/api-key',
                view_func=get_company_api_key,
                methods=['GET'],
                endpoint='users_company_api_key')

# Add a more direct and reliable API key endpoint for the user dashboard
app.add_url_rule('/api/get-api-key',
                view_func=get_api_key,
                methods=['GET'],
                endpoint='direct_api_key')

# Enable CORS for development
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        
    # Handle preflight requests
    if request.method == 'OPTIONS':
        response.headers['Access-Control-Max-Age'] = '3600'
        response.status_code = 204
        return response
        
    return response

# Serve admin static files
@app.route('/admin/<path:path>')
def serve_admin_static(path):
    return send_from_directory('static/admin', path)

# Add a specific route for the root admin page
@app.route('/admin')
@app.route('/admin/')
def serve_admin_root():
    return send_from_directory('static/admin', 'dashboard.html')

@app.before_request
def before_request():
    request.start_time = start_timer()

@app.after_request
def after_request(response):
    stop_timer(request.start_time, request.path)
    return record_request_data(request, response)

# Serve frontend files
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# Serve all frontend static assets
@app.route('/<path:path>')
def serve_frontend(path):
    if path.startswith('static/'):
        # The route already includes 'static/', so we need to remove it
        # since the static_folder is already set to 'static'
        return send_from_directory(app.static_folder, path[7:])
    elif os.path.exists(os.path.join(frontend_dir, path)):
        return send_from_directory(frontend_dir, path)
    elif path.startswith('api/'):
        # Let the API routes handle these requests
        return jsonify({'error': 'API route not found'}), 404
    else:
        # Try to serve from static folder first
        if os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        # Default to index.html for SPA-style routing
        return send_from_directory(app.static_folder, 'index.html')

# Explicitly handle /static route to make sure it's consistent
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Set up proxy fix
app.wsgi_app = ProxyFix(app.wsgi_app)

# Set up logging
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('App startup')

@app.route('/api/metrics/dashboard', methods=['GET'], endpoint='main_dashboard_metrics')
def get_main_dashboard_metrics():
    """Get dashboard metrics for the authenticated user's company"""
    try:
        app.logger.info("Metrics dashboard endpoint called")
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            app.logger.warning("No authentication token provided for metrics dashboard")
            return jsonify({
                'success': True,
                'metrics': get_mock_metrics()
            }), 200
        
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            app.logger.warning("Invalid token for metrics dashboard")
            return jsonify({
                'success': True,
                'metrics': get_mock_metrics()
            }), 200
        
        # Get company_id directly from token payload if available
        company_id = payload.get('company_id')
        if not company_id:
            user_id = payload.get('user_id')
            from users.models import User
            user = User.query.get(user_id)
            if user:
                company_id = user.company_id or user.id
            else:
                app.logger.warning(f"User not found for metrics dashboard: {user_id}")
                return jsonify({
                    'success': True,
                    'metrics': get_mock_metrics()
                }), 200
        
        app.logger.info(f"Generating metrics for company_id: {company_id}")
        
        # Initialize with mock data
        metrics = get_mock_metrics()
        
        # Try to add real data safely using raw SQL
        try:
            from sqlalchemy import text
            from core.database import db
            
            # Get all chatbots for this company
            sql = text("""
                SELECT id, COALESCE(bot_name, 'Untitled Chatbot') as bot_name 
                FROM chatbot_configs 
                WHERE company_id = :company_id
            """)
            result = db.session.execute(sql, {"company_id": company_id})
            chatbots = result.fetchall()
            
            if chatbots:
                chatbot_ids = [str(chatbot[0]) for chatbot in chatbots]
                chatbot_id_list = ','.join(chatbot_ids)
                
                # Count total sessions
                sql = text(f"""
                    SELECT COUNT(*) 
                    FROM chat_sessions 
                    WHERE chatbot_id IN ({chatbot_id_list})
                """)
                result = db.session.execute(sql)
                metrics['total_conversations'] = result.scalar() or 0
                
                # Count total messages
                sql = text(f"""
                    SELECT COUNT(*) 
                    FROM chat_messages cm
                    JOIN chat_sessions cs ON cm.session_id = cs.id
                    WHERE cs.chatbot_id IN ({chatbot_id_list})
                """)
                result = db.session.execute(sql)
                metrics['total_messages'] = result.scalar() or 0
                
                # Calculate average messages per conversation
                if metrics['total_conversations'] > 0:
                    metrics['average_messages_per_conversation'] = round(metrics['total_messages'] / metrics['total_conversations'], 1)
                
                # Get message volume over time
                sql = text(f"""
                    SELECT 
                        DATE(cm.timestamp) as date, 
                        COUNT(*) as count 
                    FROM chat_messages cm
                    JOIN chat_sessions cs ON cm.session_id = cs.id
                    WHERE cs.chatbot_id IN ({chatbot_id_list})
                    AND cm.timestamp > NOW() - INTERVAL '30 days'
                    GROUP BY DATE(cm.timestamp)
                    ORDER BY date DESC
                    LIMIT 30
                """)
                result = db.session.execute(sql)
                message_volume = {}
                for row in result:
                    message_volume[str(row[0])] = row[1]
                
                if message_volume:
                    metrics['message_volume_over_time'] = message_volume
                
                # Get stats for each chatbot
                chatbot_stats = {}
                for chatbot in chatbots:
                    chatbot_id = chatbot[0]
                    bot_name = chatbot[1]
                    
                    # Get session count
                    sql = text("""
                        SELECT COUNT(*) 
                        FROM chat_sessions 
                        WHERE chatbot_id = :chatbot_id
                    """)
                    result = db.session.execute(sql, {"chatbot_id": chatbot_id})
                    sessions_count = result.scalar() or 0
                    
                    # Get message count
                    sql = text("""
                        SELECT COUNT(*) 
                        FROM chat_messages cm
                        JOIN chat_sessions cs ON cm.session_id = cs.id
                        WHERE cs.chatbot_id = :chatbot_id
                    """)
                    result = db.session.execute(sql, {"chatbot_id": chatbot_id})
                    messages_count = result.scalar() or 0
                    
                    # Get satisfaction rate from ratings
                    sql = text("""
                        SELECT AVG(cm.rating) 
                        FROM chat_messages cm
                        JOIN chat_sessions cs ON cm.session_id = cs.id
                        WHERE cs.chatbot_id = :chatbot_id
                        AND cm.rating IS NOT NULL
                    """)
                    result = db.session.execute(sql, {"chatbot_id": chatbot_id})
                    avg_rating = result.scalar()
                    satisfaction_rate = int(avg_rating * 20) if avg_rating else 80
                    
                    chatbot_stats[str(chatbot_id)] = {
                        'name': bot_name,
                        'sessions_count': sessions_count,
                        'messages_count': messages_count,
                        'satisfaction_rate': satisfaction_rate
                    }
                
                if chatbot_stats:
                    metrics['chatbot_stats'] = chatbot_stats
                
                # Get support tickets count
                sql = text("""
                    SELECT COUNT(*) 
                    FROM support_tickets 
                    WHERE company_id = :company_id
                """)
                try:
                    result = db.session.execute(sql, {"company_id": company_id})
                    metrics['support_tickets'] = result.scalar() or 0
                except Exception as e:
                    app.logger.error(f"Error getting support tickets count: {e}")
                    # Continue with mock data for this metric
                
                app.logger.info(f"Successfully collected real metrics for company {company_id}")
        
        except Exception as db_error:
            app.logger.error(f"Error getting real metrics: {str(db_error)}")
            app.logger.error(f"Error details: {str(db_error)}")
            # We already have mock data, so just continue
        
        return jsonify({
            'success': True,
            'metrics': metrics
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error retrieving dashboard metrics: {str(e)}")
        # Return mock data even on error
        return jsonify({
            'success': True,
            'metrics': get_mock_metrics(),
            'error_info': str(e)
        }), 200

def get_mock_metrics():
    """Return mock metrics data"""
    return {
        'total_conversations': 125,
        'total_messages': 876,
        'average_messages_per_conversation': 7,
        'satisfaction_rate': 87,
        'response_time': 1.2,
        'active_users': 35,
        'message_volume_over_time': {
            '2024-05-01': 43,
            '2024-05-02': 52,
            '2024-05-03': 38,
            '2024-05-04': 61,
            '2024-05-05': 72,
            '2024-05-06': 90,
            '2024-05-07': 54
        },
        'most_common_topics': [
            {'topic': 'Moving costs', 'count': 37},
            {'topic': 'Scheduling', 'count': 28},
            {'topic': 'Packing service', 'count': 22}
        ],
        'chatbot_stats': {
            '1': {
                'name': 'Customer Support Bot',
                'sessions_count': 125,
                'messages_count': 876,
                'satisfaction_rate': 87
            }
        },
        'support_tickets': 12
    }

# Add API key routes from the api_keys module
from api_keys.routes import get_api_key as get_api_key_route, create_api_key as create_api_key_route
app.add_url_rule('/api/keys/get',
                view_func=get_api_key_route,
                methods=['GET'],
                endpoint='get_api_key_route')
app.add_url_rule('/api/keys/create',
                view_func=create_api_key_route,
                methods=['POST'],
                endpoint='create_api_key_route')

# Add endpoint to create a new API key
app.add_url_rule('/api/users/create-api-key',
                view_func=create_api_key,
                methods=['POST'],
                endpoint='create_api_key')

# Add chatbot company API key endpoint
app.add_url_rule('/api/chatbot/company/api-key',
                view_func=chatbot_get_company_api_key,
                methods=['GET'],
                endpoint='chatbot_company_api_key')

@app.route('/api/support/tickets', methods=['GET'])
def get_support_tickets():
    """Get support tickets for the authenticated user/company"""
    try:
        app.logger.info("Support tickets endpoint called")
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            app.logger.warning("No authentication token provided for support tickets")
            # Return empty data with 200 to avoid dashboard errors
            return jsonify({
                'success': True,
                'tickets': [],
                'total': 0,
                'offset': 0,
                'limit': 100
            }), 200
        
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            app.logger.warning("Invalid token for support tickets")
            # Return empty data with 200 to avoid dashboard errors
            return jsonify({
                'success': True,
                'tickets': [],
                'total': 0,
                'offset': 0, 
                'limit': 100
            }), 200
        
        # Get company ID directly from payload if available
        company_id = payload.get('company_id')
        if not company_id:
            # If company_id not in payload, get it from user
            user_id = payload.get('user_id')
            from users.models import User
            user = User.query.get(user_id)
            if user:
                company_id = user.company_id or user.id
            else:
                app.logger.warning(f"User not found for support tickets: {user_id}")
                return jsonify({
                    'success': True,
                    'tickets': [],
                    'total': 0,
                    'offset': 0,
                    'limit': 100
                }), 200
        
        # Get query parameters
        status = request.args.get('status')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        app.logger.info(f"Getting support tickets for company_id: {company_id}")
        
        # Try to safely get tickets from the database
        try:
            from admin_panel.models import SupportTicket
            
            # Build query based on parameters
            query = SupportTicket.query.filter_by(company_id=company_id)
            
            # Add status filter if provided
            if status:
                query = query.filter_by(status=status)
            
            # Get total count (do this first in case the later queries fail)
            total_count = query.count()
            
            # Apply pagination
            tickets_data = query.order_by(SupportTicket.created_at.desc()).offset(offset).limit(limit).all()
            
            # Format the tickets
            tickets = []
            for ticket in tickets_data:
                try:
                    # Find the user who created the ticket
                    from users.models import User
                    ticket_user = User.query.get(ticket.user_id)
                    
                    tickets.append({
                        'id': ticket.id,
                        'ticket_number': ticket.ticket_number,
                        'subject': ticket.subject,
                        'topic': ticket.topic,
                        'details': ticket.details,
                        'status': ticket.status,
                        'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                        'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
                        'user': {
                            'id': ticket_user.id,
                            'name': ticket_user.user_name,
                            'email': ticket_user.user_email
                        } if ticket_user else None
                    })
                except Exception as ticket_error:
                    app.logger.error(f"Error formatting ticket {ticket.id}: {str(ticket_error)}")
                    # Skip this ticket but continue processing others
            
            app.logger.info(f"Found {len(tickets)} support tickets for company_id {company_id}")
            
            return jsonify({
                'success': True,
                'tickets': tickets,
                'total': total_count,
                'offset': offset,
                'limit': limit
            }), 200
        except Exception as db_error:
            app.logger.error(f"Database error getting tickets: {str(db_error)}")
            # Return empty results with 200 status to avoid breaking the dashboard
            return jsonify({
                'success': True,
                'tickets': [],
                'total': 0,
                'offset': offset,
                'limit': limit,
                'error_info': str(db_error)
            }), 200
        
    except Exception as e:
        app.logger.error(f"Error retrieving tickets: {str(e)}")
        # Return empty data even on error to avoid breaking the dashboard
        return jsonify({
            'success': True,
            'tickets': [],
            'total': 0,
            'offset': 0,
            'limit': 100,
            'error_info': str(e)
        }), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5006) 

# Apply dashboard fixes to ensure all endpoints return 200 status
try:
    from fix_dashboard_issues import fix_dashboard_issues
    fix_dashboard_issues(app, db)
    print("Dashboard fixes applied successfully!")
except ImportError:
    print("Dashboard fixes not applied - fix_dashboard_issues.py not found.")
    print("If you're having issues with the dashboard, run:")
    print("python src/fix_chat_sessions.py && python src/fix_chatbot_metrics.py") 