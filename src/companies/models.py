from core.database import db
from datetime import datetime

class Company(db.Model):
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    website = db.Column(db.String(200))
    business_address = db.Column(db.Text)
    niche = db.Column(db.String(100))
    subscription_plan = db.Column(db.String(20), default='basic')  # basic, pro, enterprise
    status = db.Column(db.String(20), default='active')  # active, inactive, suspended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tickets = db.relationship('SupportTicket', backref='company', lazy=True)
    chatbots = db.relationship('Chatbot', back_populates='company', lazy=True)
    feature_settings = db.relationship('CompanyFeatureSettings', backref='company', uselist=False)
    moving_parameters = db.relationship('MovingParameters', backref='company', uselist=False)
    moving_quote_requests = db.relationship('MovingQuoteRequest', backref='company', lazy=True)

class CompanyFeatureSettings(db.Model):
    __tablename__ = 'company_feature_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    enabled_features = db.Column(db.JSON, default=lambda: {
        'chatbot': True,
        'knowledge_base': True,
        'support_tickets': True,
        'api_access': False,
        'custom_branding': False,
        'analytics': False,
        'multi_language': False,
        'advanced_ai': False,
        'priority_support': False,
        'custom_integrations': False,
        'moving_calculator': False
    })
    feature_limits = db.Column(db.JSON, default=lambda: {
        'knowledge_base_documents': 50,
        'support_tickets_per_month': 10,
        'api_calls_per_month': 0,
        'languages': 1
    })
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    company = db.relationship('Company', back_populates='chatbots')
    messages = db.relationship('Message', backref='chatbot', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Chatbot {self.name} for Company {self.company_id}>'

class MovingParameters(db.Model):
    """Parameters for moving companies to calculate cost estimates"""
    __tablename__ = 'moving_parameters'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    
    # Base rate per mile
    base_rate_per_mile = db.Column(db.Float, default=1.50)
    
    # JSON field for move size rates
    move_size_rates = db.Column(db.JSON, default=lambda: {
        "studio": 320,
        "1-bedroom": 640, 
        "2-bedroom": 960,
        "3-bedroom": 1280,
        "4-bedroom": 1600,
        "office": 2000,
        "car": 120
    })
    
    # JSON field for additional service costs
    additional_service_costs = db.Column(db.JSON, default=lambda: {
        "packing": {
            "studio": 100,
            "1-bedroom": 150,
            "2-bedroom": 200,
            "3-bedroom": 250,
            "4-bedroom": 300,
            "office": 350,
            "car": 50
        },
        "storage": {
            "studio": 80,
            "1-bedroom": 130,
            "2-bedroom": 180,
            "3-bedroom": 230,
            "4-bedroom": 280,
            "office": 300,
            "car": 50
        }
    })
    
    # JSON field for rate adjustments
    rate_adjustments = db.Column(db.JSON, default=lambda: {
        "seasonality_rate": 0.10,
        "rural_location_rate": 0.10,
        "min_cost_multiplier": 1.1,
        "max_cost_multiplier": 1.4
    })
    
    # JSON field for email configuration
    email_config = db.Column(db.JSON, default=lambda: {
        "smtp": {
            "server": "smtp.gmail.com",
            "port": 587,
            "username": "info@movergpt.com",
            "password": "yuip pxze ammd xxym",
            "staff_email": "jackdev24code@gmail.com"
        },
        "staff_email_subject": "New Moving Request from {{customer_name}}",
        "staff_email_template": """New Moving Request

Customer Information:\n
- Name: {{customer_name}}\n
- Email: {{customer_email}}\n
- Phone: {{customer_phone}}\n

Moving Details:\n
- From: {{origin}}\n
- To: {{destination}}\n
- Moving Date: {{move_date}}\n
- Move Size: {{move_size}}\n
- Distance: {{distance_miles}} miles\n
- Additional Services: {{additional_services}}\n

Cost Breakdown:\n
- Base Rate: ${{base_rate}}\n
- Distance Cost: ${{distance_cost}}\n
- Services Cost: ${{services_cost}}\n
- Adjustments: ${{adjustments}}\n
- Total Cost: ${{total_cost}}\n

Booking Reference: {{booking_reference}}\n

Please contact the customer as soon as possible to confirm the booking.""",
        "customer_email_template": """Dear {{customer_name}},\n

Thank you for requesting a moving quote with My Moving Journey!\n

Here are the details of your request:\n
- From: {{origin}}\n
- To: {{destination}}\n
- Moving Date: {{move_date}}\n
- Move Size: {{move_size}}\n
- Additional Services: {{additional_services}}\n

Your estimated cost is ${{total_cost}}.\n

We will contact you shortly to confirm your booking. If you have any questions, please reply to this email or call us.\n

Thank you for choosing My Moving Journey!\n

Best regards,\n
The Moving Team\n
info@movergpt.com"""

# Best regards,
# The Moving Team
# info@movergpt.com"""
    })
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MovingQuoteRequest(db.Model):
    """Stores form submissions from the moving cost calculator"""
    __tablename__ = 'moving_quote_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    
    # Step 1: Origin and Destination
    origin = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    
    # Step 2: Distance and Move Details
    distance_miles = db.Column(db.Float, nullable=False)
    move_size = db.Column(db.String(50), nullable=False)  # studio, 1-bedroom, etc.
    move_date = db.Column(db.Date, nullable=False)
    
    # Step 3: Contact Information
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    recipient_email = db.Column(db.String(120))  # Email to receive estimate details
    notes = db.Column(db.Text)  # Additional notes from customer or internal notes
    
    # Quote Details
    total_cost = db.Column(db.Float, nullable=False)
    base_rate = db.Column(db.Float)
    distance_cost = db.Column(db.Float)
    size_cost = db.Column(db.Float)
    services_cost = db.Column(db.Float, default=0.0)
    adjustments = db.Column(db.Float, default=0.0)
    
    # Additional Services
    additional_services = db.Column(db.JSON, default=lambda: {})
    
    # Status
    status = db.Column(db.String(20), default='new')  # new, contacted, confirmed, canceled
    
    # Tracking
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    referrer = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<MovingQuoteRequest {self.id} for Company {self.company_id}>' 