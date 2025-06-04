"""
API Keys routes
Provides endpoints for managing API keys
"""

import secrets
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from api_keys.models import ApiKey
from core.database import db
from core.utils import verify_jwt

api_keys_bp = Blueprint('api_keys', __name__)
logger = logging.getLogger(__name__)

@api_keys_bp.route('/create', methods=['POST'])
def create_api_key():
    """Create a new API key for the current user's company"""
    logger.info("Creating new API key")
    
    # Check authentication
    token = request.cookies.get('access_token')
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    
    if not token:
        return jsonify({"error": "Authentication required", "success": False}), 401
    
    # Verify token
    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid token", "success": False}), 401
    
    # Get company ID from token or user
    user_id = payload.get('user_id')
    company_id = payload.get('company_id')
    
    if not company_id and user_id:
        # Try to get company ID from user record
        try:
            from users.models import User
            user = User.query.get(user_id)
            if user and hasattr(user, 'company_id') and user.company_id:
                company_id = user.company_id
            else:
                # If still no company_id, use user_id as fallback
                company_id = user_id
        except Exception as e:
            logger.warning(f"Error getting company ID from user: {str(e)}")
            company_id = user_id
    
    if not company_id:
        return jsonify({"error": "No company ID found", "success": False}), 400
    
    try:
        # Generate new API key
        api_key = f"sk_{secrets.token_hex(24)}"
        
        # Create new ApiKey object
        new_key = ApiKey(
            company_id=company_id,
            key=api_key,
            status='active',
            created_at=datetime.utcnow()
        )
        
        # Save to database
        db.session.add(new_key)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "API key created successfully",
            "api_key": api_key,
            "company_id": company_id
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating API key: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Error creating API key: {str(e)}"
        }), 500

@api_keys_bp.route('/get', methods=['GET'])
def get_api_key():
    """Get the API key for the current user's company"""
    logger.info("Getting API key")
    
    # Check authentication
    token = request.cookies.get('access_token')
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    
    if not token:
        return jsonify({"error": "Authentication required", "success": False}), 401
    
    # Verify token
    payload = verify_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid token", "success": False}), 401
    
    # Get company ID from token or user
    user_id = payload.get('user_id')
    company_id = payload.get('company_id')
    
    if not company_id and user_id:
        # Try to get company ID from user record
        try:
            from users.models import User
            user = User.query.get(user_id)
            if user and hasattr(user, 'company_id') and user.company_id:
                company_id = user.company_id
            else:
                # If still no company_id, use user_id as fallback
                company_id = user_id
        except Exception as e:
            logger.warning(f"Error getting company ID from user: {str(e)}")
            company_id = user_id
    
    if not company_id:
        return jsonify({"error": "No company ID found", "success": False}), 400
    
    try:
        # Get API key from database
        api_key_obj = ApiKey.query.filter_by(
            company_id=company_id,
            status='active'
        ).order_by(ApiKey.created_at.desc()).first()
        
        if not api_key_obj:
            # Create a new API key if none exists
            api_key = f"sk_{secrets.token_hex(24)}"
            
            # Create new ApiKey object
            api_key_obj = ApiKey(
                company_id=company_id,
                key=api_key,
                status='active',
                created_at=datetime.utcnow()
            )
            
            # Save to database
            db.session.add(api_key_obj)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "New API key created",
                "api_key": api_key_obj.key,
                "company_id": company_id
            })
        
        return jsonify({
            "success": True,
            "message": "API key retrieved",
            "api_key": api_key_obj.key,
            "company_id": company_id
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error getting API key: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Error getting API key: {str(e)}"
        }), 500 