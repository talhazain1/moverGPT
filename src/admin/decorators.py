from functools import wraps
from flask import jsonify, request, session
from admin.models import AdminUser, AdminRole, AdminPermission

def require_admin_role(role: AdminRole):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            admin_id = session.get('admin_id')
            if not admin_id:
                return jsonify({"error": "Not authenticated"}), 401
            
            admin = AdminUser.query.get(admin_id)
            if not admin or not admin.has_role(role):
                return jsonify({"error": "Insufficient permissions"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_admin_permission(permission: AdminPermission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            admin_id = session.get('admin_id')
            if not admin_id:
                return jsonify({"error": "Not authenticated"}), 401
            
            admin = AdminUser.query.get(admin_id)
            if not admin or not admin.has_permission(permission):
                return jsonify({"error": "Insufficient permissions"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator 