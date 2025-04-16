from flask import Flask, send_from_directory
import os
from flask import request
from core.database import db, init_db
from flask_migrate import Migrate
from core.monitoring import metrics_endpoint, record_request_data, start_timer, stop_timer
from users.views import users_bp
from admin.routes import admin_bp
from admin_panel.routes import admin_panel, support
from chatbot.views import chatbot_bp, admin_chatbots_bp
from payments.webhook import stripe_webhook
from payments.routes import payments_bp
from chatbot.session_views import session_bp
from core.metrics_api import metrics_bp
from subscriptions import subscriptions_bp
from datetime import timedelta
from flask_login import LoginManager
from admin.models import AdminUser

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Database configuration
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session configuration
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "default_secret_key")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin.login'

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

init_db(app)
migrate = Migrate(app, db)

# Register blueprints
app.register_blueprint(users_bp, url_prefix="/api/users")
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(admin_panel, url_prefix="/api/admin/panel")
app.register_blueprint(support, url_prefix="/api/support")
app.register_blueprint(chatbot_bp, url_prefix="/api/chatbot")
app.register_blueprint(admin_chatbots_bp, url_prefix="/api/admin/chatbots")
app.register_blueprint(session_bp, url_prefix="/api/chatbot")
app.register_blueprint(payments_bp, url_prefix="/api/payments")
app.add_url_rule("/api/payments/webhook", view_func=stripe_webhook, methods=["POST"])
app.register_blueprint(metrics_bp, url_prefix="/api/metrics")
app.register_blueprint(subscriptions_bp, url_prefix='/api/subscriptions')

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

@app.before_request
def before_request():
    request.start_time = start_timer()

@app.after_request
def after_request(response):
    stop_timer(request.start_time, request.path)
    return record_request_data(request, response)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    debug_mode = os.environ.get("DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode) 