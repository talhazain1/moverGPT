from functools import wraps
from flask import request, jsonify
from core.database import db
from companies.models import CompanyFeatureSettings

def require_feature(feature_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get company_id from the request context or URL parameters
            company_id = request.args.get('company_id') or request.view_args.get('company_id')
            if not company_id:
                return jsonify({'error': 'Company ID is required'}), 400
            
            # Get feature settings
            settings = CompanyFeatureSettings.query.filter_by(company_id=company_id).first()
            if not settings:
                return jsonify({'error': 'Feature settings not found'}), 404
            
            # Check if feature is enabled
            if not settings.enabled_features.get(feature_name, False):
                return jsonify({'error': f'Feature {feature_name} is not enabled for this company'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_feature_limit(feature_name, limit_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get company_id from the request context or URL parameters
            company_id = request.args.get('company_id') or request.view_args.get('company_id')
            if not company_id:
                return jsonify({'error': 'Company ID is required'}), 400
            
            # Get feature settings
            settings = CompanyFeatureSettings.query.filter_by(company_id=company_id).first()
            if not settings:
                return jsonify({'error': 'Feature settings not found'}), 404
            
            # Check if feature is enabled
            if not settings.enabled_features.get(feature_name, False):
                return jsonify({'error': f'Feature {feature_name} is not enabled for this company'}), 403
            
            # Get current usage
            current_usage = get_current_usage(company_id, feature_name, limit_name)
            
            # Get limit
            limit = settings.feature_limits.get(limit_name, 0)
            
            # Check if limit is exceeded
            if limit != float('inf') and current_usage >= limit:
                return jsonify({'error': f'{limit_name} limit exceeded'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_usage(company_id, feature_name, limit_name):
    # This function should be implemented based on your specific needs
    # For example, you might want to count:
    # - Number of knowledge base documents
    # - Number of support tickets this month
    # - Number of API calls this month
    # - Number of languages configured
    return 0  # Placeholder implementation 