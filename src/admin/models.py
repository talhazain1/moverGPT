from core.database import db
from datetime import datetime
from enum import Enum
from flask_login import UserMixin

class AdminRole(Enum):
    SUPER_ADMIN = "super_admin"
    SUPPORT = "support"
    ACCOUNTS = "accounts"
    BACKEND = "backend"

class AdminPermission(Enum):
    # Company Management
    VIEW_COMPANIES = "view_companies"
    MANAGE_COMPANIES = "manage_companies"
    
    # Payment Management
    VIEW_PAYMENTS = "view_payments"
    MANAGE_PAYMENTS = "manage_payments"
    
    # API Management
    VIEW_APIS = "view_apis"
    MANAGE_APIS = "manage_apis"
    
    # Support Management
    VIEW_SUPPORT = "view_support"
    MANAGE_SUPPORT = "manage_support"
    
    # Admin Management
    VIEW_ADMINS = "view_admins"
    MANAGE_ADMINS = "manage_admins"

class AdminRoleModel(db.Model):
    __tablename__ = 'admin_roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.Column(db.JSON)  # Store permissions as JSON array
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_permissions(self):
        """Get list of permission values."""
        return self.permissions or []

class AdminUser(db.Model, UserMixin):
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    role_id = db.Column(db.Integer, db.ForeignKey('admin_roles.id'))
    role = db.relationship('AdminRoleModel', backref='admin_users')
    company = db.relationship('Company', backref='admin_users')
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        """Set the password hash."""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the provided password matches the hash."""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def get_permissions(self):
        """Get list of permissions for the user."""
        if not self.role:
            return []
        return self.role.get_permissions()
    
    def has_permission(self, permission: AdminPermission) -> bool:
        """Check if admin has a specific permission."""
        if not self.role:
            return False
        return permission.value in self.get_permissions()
    
    def has_role(self, role: AdminRole) -> bool:
        """Check if admin has a specific role."""
        return self.role and self.role.name == role.value 

class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    company = db.relationship('Company', backref='api_keys_admin')
    subscription_plan = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, inactive, revoked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    @property
    def is_active(self):
        """Check if the API key is active based on status"""
        return self.status == 'active'
    
    def __repr__(self):
        return f'<ApiKey {self.key[:8]}... for Company {self.company_id}>' 