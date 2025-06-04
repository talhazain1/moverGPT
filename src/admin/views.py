import uuid
import secrets
import string
from datetime import datetime
from flask import jsonify, request, current_app
from admin.routes import admin_bp
from core.database import db
from admin.models import ApiKey
from companies.models import Company
from core.utils import verify_jwt

@admin_bp.route('/api-keys/generate', methods=['POST'])
def generate_api_key():
    current_app.logger.info("Entered generate_api_key")
    
    # Check admin authentication
    user_data = verify_jwt()
    if not user_data or not user_data.get('is_admin'):
        current_app.logger.warning("Non-admin attempted to generate API key")
        return jsonify({
            'success': False,
            'error': 'Admin authentication required',
            'response': 'You must be logged in as an administrator to perform this action.'
        }), 401
    
    # Get company ID from request
    data = request.get_json()
    company_id = data.get('company_id')
    
    if not company_id:
        current_app.logger.warning("No company_id provided in request")
        return jsonify({
            'success': False,
            'error': 'Missing company_id',
            'response': 'Company ID is required to generate an API key.'
        }), 400
    
    try:
        # Check if company exists
        company = db.session.query(Company).filter_by(id=company_id).first()
        if not company:
            current_app.logger.warning(f"Company not found: company_id={company_id}")
            return jsonify({
                'success': False,
                'error': 'Company not found',
                'response': f'No company found with ID {company_id}.'
            }), 404
        
        # Generate a new API key
        api_key = generate_secure_api_key()
        
        # Deactivate existing API keys for this company
        try:
            existing_keys = db.session.query(ApiKey).filter_by(company_id=company_id, active=True).all()
            for key in existing_keys:
                key.active = False
                key.revoked_at = datetime.utcnow()
                db.session.add(key)
        except Exception as e:
            current_app.logger.error(f"Error deactivating existing API keys: {e}")
            # Continue with new key creation even if deactivation fails
        
        # Create and store the new API key
        new_api_key = ApiKey(
            company_id=company_id,
            key=api_key,
            active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(new_api_key)
        db.session.commit()
        
        current_app.logger.info(f"Generated new API key for company_id={company_id}")
        return jsonify({
            'success': True,
            'message': 'API key generated successfully',
            'api_key': api_key,
            'company_id': company_id,
            'created_at': new_api_key.created_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generating API key: {e}")
        return jsonify({
            'success': False,
            'error': f"Error generating API key: {str(e)}",
            'response': 'An error occurred while generating the API key.'
        }), 500

# Helper function to generate a secure API key
def generate_secure_api_key():
    # Generate a JWT-like structure (header.payload.signature)
    random_chars = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    timestamp = int(datetime.utcnow().timestamp())
    header = uuid.uuid4().hex[:8]
    payload = f"{timestamp}.{random_chars}"
    signature = uuid.uuid4().hex[:16]
    
    return f"{header}.{payload}.{signature}" 