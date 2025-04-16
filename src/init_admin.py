from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from enum import Enum

# Create Flask app
app = Flask(__name__)
app.config.from_object('core.config.Config')

# Initialize SQLAlchemy
db = SQLAlchemy()
db.init_app(app)

class AdminRole(Enum):
    SUPER_ADMIN = 'super_admin'
    SUPPORT = 'support'
    ACCOUNTS = 'accounts'
    BACKEND = 'backend'

class AdminPermission(Enum):
    VIEW_COMPANIES = 'view_companies'
    VIEW_SUPPORT = 'view_support'
    MANAGE_SUPPORT = 'manage_support'
    VIEW_PAYMENTS = 'view_payments'
    MANAGE_PAYMENTS = 'manage_payments'
    VIEW_APIS = 'view_apis'
    MANAGE_APIS = 'manage_apis'

# Define models
class AdminRoleModel(db.Model):
    __tablename__ = 'admin_roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.Column(db.JSON)

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    role_id = db.Column(db.Integer, db.ForeignKey('admin_roles.id'))
    is_active = db.Column(db.Boolean, default=True)

def init_admin_roles():
    """Initialize admin roles and permissions"""
    # Create roles if they don't exist
    roles = {
        AdminRole.SUPER_ADMIN.value: {
            'description': 'Super Admin with all permissions',
            'permissions': [p.value for p in AdminPermission]
        },
        AdminRole.SUPPORT.value: {
            'description': 'Support team member',
            'permissions': [
                AdminPermission.VIEW_COMPANIES.value,
                AdminPermission.VIEW_SUPPORT.value,
                AdminPermission.MANAGE_SUPPORT.value
            ]
        },
        AdminRole.ACCOUNTS.value: {
            'description': 'Accounts team member',
            'permissions': [
                AdminPermission.VIEW_COMPANIES.value,
                AdminPermission.VIEW_PAYMENTS.value,
                AdminPermission.MANAGE_PAYMENTS.value
            ]
        },
        AdminRole.BACKEND.value: {
            'description': 'Backend team member',
            'permissions': [
                AdminPermission.VIEW_APIS.value,
                AdminPermission.MANAGE_APIS.value
            ]
        }
    }

    for role_name, role_data in roles.items():
        role = AdminRoleModel.query.filter_by(name=role_name).first()
        if not role:
            role = AdminRoleModel(
                name=role_name,
                description=role_data['description'],
                permissions=role_data['permissions']
            )
            db.session.add(role)
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Initialize roles
        init_admin_roles()
        
        print("Admin initialization completed successfully!")
        print("Database and roles have been initialized.")
        print("You can now create a super admin user through the setup page.") 