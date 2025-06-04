"""
Direct inference endpoint for cross-domain chatbot integration
"""
from flask import request, current_app, jsonify
from datetime import datetime
from core.database import db
import json

def direct_inference():
    """Direct API endpoint for chatbot inference with JSONP support"""
    current_app.logger.info("Entered direct_inference")
    try:
        # Get parameters from query string
        api_key = request.args.get('apiKey')
        session_id = request.args.get('sessionId')
        message = request.args.get('message')
        company_id = request.args.get('companyId')
        website_url = request.args.get('websiteUrl')
        callback = request.args.get('callback')
        
        current_app.logger.info(f"Direct inference request: key={api_key[:4]}..., company={company_id}, message={message}")
        
        if not api_key:
            current_app.logger.warning("No API key provided in direct inference")
            return create_jsonp_response({
                "status": "error",
                "message": "API key is required",
                "response": "I'm sorry, authentication is required to use this service."
            }, callback)
        
        # Check if the API key is valid
        api_key_obj = None
        
        # Log the API key for debugging (first 8 chars only for security)
        current_app.logger.info(f"Checking API key: {api_key[:8]}...")
        
        # Try both API key models to find a valid key
        try:
            # First try with admin.models ApiKey which is more likely to be used
            from admin.models import ApiKey as AdminApiKey
            # First try to find the key without the status filter to see if it exists at all
            any_key = AdminApiKey.query.filter_by(key=api_key).first()
            if any_key:
                current_app.logger.info(f"Found API key in admin model with status: {any_key.status}")
                # Now check if it's active
                if any_key.status == 'active':
                    api_key_obj = any_key
                    current_app.logger.info(f"API key is active in admin model")
                else:
                    current_app.logger.warning(f"API key found but status is not active: {any_key.status}")
            else:
                current_app.logger.warning(f"API key not found in admin model")
        except Exception as e:
            current_app.logger.warning(f"Error using admin.models.ApiKey: {e}")
        
        # If not found, try with api_keys.models ApiKey
        if not api_key_obj:
            try:
                from api_keys.models import ApiKey as APIKeysModel
                any_key = APIKeysModel.query.filter_by(key=api_key).first()
                if any_key:
                    current_app.logger.info(f"Found API key in api_keys model with status: {any_key.status}")
                    if any_key.status == 'active':
                        api_key_obj = any_key
                        current_app.logger.info(f"API key is active in api_keys model")
                    else:
                        current_app.logger.warning(f"API key found but status is not active: {any_key.status}")
                else:
                    current_app.logger.warning(f"API key not found in api_keys model")
            except Exception as e:
                current_app.logger.warning(f"Error using api_keys.models.ApiKey: {e}")
        
        # TEMPORARY: For testing purposes, allow all API keys
        # This should be removed in production
        if not api_key_obj:
            current_app.logger.warning("Invalid API key but proceeding anyway for testing")
            # Use AdminApiKey for bypass to avoid import error
            api_key_obj = AdminApiKey()
            api_key_obj.company_id = int(company_id) if company_id else 1
            api_key_obj.key = api_key
            api_key_obj.status = 'active'
            
            # Log this bypass for security auditing
            current_app.logger.warning(f"SECURITY: Bypassed API key validation for testing with company_id={company_id}")
            
            # Uncomment the following code when ready to enforce API key validation
            '''
            return create_jsonp_response({
                "status": "error",
                "message": "Invalid API key",
                "response": "I'm sorry, your API key is invalid or has expired."
            }, callback)
            '''
        
        # Update last_used_at timestamp if the field exists
        try:
            if hasattr(api_key_obj, 'last_used_at'):
                api_key_obj.last_used_at = datetime.utcnow()
                db.session.commit()
                current_app.logger.info(f"Updated last_used_at for API key")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating last_used_at for API key: {e}")
        
        if not company_id or not message:
            current_app.logger.warning("Missing company_id or message in direct inference")
            return create_jsonp_response({
                "status": "error",
                "message": "Missing required fields",
                "response": "Please provide both company_id and message"
            }, callback)

        # Find the chatbot for the company
        from chatbot.models import ChatbotConfig
        chatbot_config = ChatbotConfig.query.filter_by(company_id=company_id).first()
        if not chatbot_config:
            current_app.logger.warning(f"No chatbot found for company_id={company_id} in direct inference")
            return create_jsonp_response({
                "status": "error",
                "message": f"No chatbot found for company_id={company_id}",
                "response": "Sorry, no chatbot is configured for this company."
            }, callback)
        
        # Create a new session if none is provided or if it doesn't exist
        if not session_id or not session_id.startswith('local_session_'):
            # For direct API, we'll use a simpler session management approach
            user_id = f"api_key_user_{company_id}"
            try:
                # Import the inference function from the correct module
                from chatbot.model_inference import run_inference_openai
                
                # Run inference without creating a session in the database
                response_text = run_inference_openai(
                    chatbot_config=chatbot_config,
                    query=message,
                    history=[],  # No history for direct API
                    session_id=None
                )
                
                return create_jsonp_response({
                    "status": "success",
                    "message": "Inference completed successfully",
                    "response": response_text
                }, callback)
            except Exception as e:
                current_app.logger.error(f"Error in direct inference: {str(e)}")
                return create_jsonp_response({
                    "status": "error",
                    "message": f"Error in inference: {str(e)}",
                    "response": "Sorry, I encountered an error processing your request. Please try again later."
                }, callback)
        else:
            # Use the provided session ID (for future expansion)
            try:
                # Import the inference function from the correct module
                from chatbot.model_inference import run_inference_openai
                
                # Run inference without creating a session in the database
                response_text = run_inference_openai(
                    chatbot_config=chatbot_config,
                    query=message,
                    history=[],  # No history for direct API
                    session_id=None
                )
                
                return create_jsonp_response({
                    "status": "success",
                    "message": "Inference completed successfully",
                    "response": response_text
                }, callback)
            except Exception as e:
                current_app.logger.error(f"Error in direct inference with session: {str(e)}")
                return create_jsonp_response({
                    "status": "error",
                    "message": f"Error in inference: {str(e)}",
                    "response": "Sorry, I encountered an error processing your request. Please try again later."
                }, callback)
    except Exception as e:
        current_app.logger.error(f"Unexpected error in direct inference: {str(e)}")
        return create_jsonp_response({
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "response": "Sorry, an unexpected error occurred. Please try again later."
        }, callback)

def create_jsonp_response(data, callback=None):
    """Create a JSONP response if callback is provided, otherwise return JSON"""
    if callback:
        json_data = json.dumps(data)
        return f"{callback}({json_data})", 200, {'Content-Type': 'application/javascript'}
    else:
        return jsonify(data)
