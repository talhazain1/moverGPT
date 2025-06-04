from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from core.database import db
from core.utils import verify_jwt
from companies.models import Company, MovingParameters, MovingQuoteRequest
import logging
from datetime import datetime
import re
from services.email_service import EmailService, apply_template

# Set up the companies blueprint
companies_bp = Blueprint('companies', __name__)
logger = logging.getLogger(__name__)

@companies_bp.route('/<int:company_id>/moving-parameters', methods=['GET'], endpoint='get_moving_parameters')
def get_moving_parameters(company_id):
    """
    Get moving parameters for a specific company
    """
    logger.info(f"Received request for moving parameters for company_id: {company_id}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request cookies: {dict(request.cookies)}")
    
    try:
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            logger.info("Found token in Authorization header")
        else:
            token = request.cookies.get("access_token")
            logger.info("Found token in cookies")
        
        if not token:
            logger.warning("No token found in request")
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            logger.warning("Token verification failed")
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        logger.info(f"Token verified successfully. Payload: {payload}")
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        
        # If user not found, try to get user by company_id
        if not user:
            logger.warning(f"User not found for ID: {payload.get('user_id')}, trying to find user by company_id")
            user = User.query.filter_by(company_id=company_id).first()
            if not user:
                logger.warning(f"No user found for company_id: {company_id}")
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404
        
        # Check if user has access to the requested company
        user_company_id = user.company_id or user.id
        logger.info(f"User company ID: {user_company_id}, Requested company ID: {company_id}")
        
        # Allow access if user is admin or belongs to the company
        is_admin = False
        try:
            from admin.models import AdminUser
            is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
            logger.info(f"User is admin: {is_admin}")
        except:
            pass
            
        if not is_admin and user_company_id != company_id:
            logger.warning(f"Access denied: user_company_id ({user_company_id}) != requested company_id ({company_id})")
            return jsonify({
                'success': False,
                'error': 'You do not have access to this company'
            }), 403
        
        # Get moving parameters
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        logger.info(f"Found moving parameters: {params is not None}")
        
        # If no parameters exist yet, create default ones
        if not params:
            logger.info("Creating default moving parameters")
            params = MovingParameters(
                company_id=company_id,
                base_rate_per_mile=1.50,
                move_size_rates={
                    'studio': 320,
                    '1-bedroom': 640,
                    '2-bedroom': 960,
                    '3-bedroom': 1280,
                    '4-bedroom': 1600,
                    'office': 2000,
                    'car': 120
                },
                additional_service_costs={
                    'packing': {
                        'studio': 100,
                        '1-bedroom': 150,
                        '2-bedroom': 200,
                        '3-bedroom': 250,
                        '4-bedroom': 300,
                        'office': 350,
                        'car': 50
                    },
                    'storage': {
                        'studio': 80,
                        '1-bedroom': 130,
                        '2-bedroom': 180,
                        '3-bedroom': 230,
                        '4-bedroom': 280,
                        'office': 300,
                        'car': 50
                    }
                },
                rate_adjustments={
                    'seasonality_rate': 0.10,
                    'rural_location_rate': 0.10,
                    'max_cost_multiplier': 1.2,
                    'min_cost_multiplier': 0.8
                }
            )
            db.session.add(params)
            try:
                db.session.commit()
                logger.info(f"Created default moving parameters for company {company_id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating default parameters: {str(e)}")
                raise

        return jsonify({
            'success': True,
            'parameters': {
                'base_rate_per_mile': params.base_rate_per_mile,
                'move_size_rates': params.move_size_rates,
                'additional_service_costs': params.additional_service_costs,
                'rate_adjustments': params.rate_adjustments,
                'email_config': params.email_config
            }
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error retrieving moving parameters: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Database error occurred'
        }), 500
    except Exception as e:
        logger.error(f"Error retrieving moving parameters: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/save-moving-parameters', methods=['PUT'])
def save_moving_parameters():
    """
    Save moving parameters for a company
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get company ID from query parameters or request data
        company_id = request.args.get('company_id') or data.get('company_id')
        if not company_id:
            return jsonify({
                'success': False,
                'error': 'Company ID is required'
            }), 400
        
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Check if user has access to the requested company
        user_company_id = user.company_id or user.id
        
        # Allow access if user is admin or belongs to the company
        is_admin = False
        try:
            from admin.models import AdminUser
            is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
        except:
            pass
            
        if not is_admin and user_company_id != int(company_id):
            return jsonify({
                'success': False,
                'error': 'You do not have access to this company'
            }), 403
        
        # Get or create moving parameters
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        if not params:
            params = MovingParameters(company_id=company_id)
            db.session.add(params)
        
        # Update parameters
        if 'base_rate_per_mile' in data:
            params.base_rate_per_mile = float(data['base_rate_per_mile'])
        if 'move_size_rates' in data:
            params.move_size_rates = data['move_size_rates']
        if 'additional_service_costs' in data:
            params.additional_service_costs = data['additional_service_costs']
        if 'rate_adjustments' in data:
            params.rate_adjustments = data['rate_adjustments']
        if 'email_config' in data:
            params.email_config = data['email_config']
        
        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Parameters saved successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Error saving parameters: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/<int:company_id>/moving-parameters/reset', methods=['POST'])
def reset_moving_parameters(company_id):
    """
    Reset moving parameters for a company to default values
    """
    try:
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Check if user has access to the requested company
        user_company_id = user.company_id or user.id
        
        # Allow access if user is admin or belongs to the company
        is_admin = False
        try:
            from admin.models import AdminUser
            is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
        except:
            pass
            
        if not is_admin and user_company_id != company_id:
            return jsonify({
                'success': False,
                'error': 'You do not have access to this company'
            }), 403
        
        # Get or create moving parameters
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        if not params:
            params = MovingParameters(company_id=company_id)
            db.session.add(params)
        
        # Reset to default values
        params.base_rate_per_mile = 1.50
        params.move_size_rates = {
            'studio': 320,
            '1-bedroom': 640,
            '2-bedroom': 960,
            '3-bedroom': 1280,
            '4-bedroom': 1600,
            'office': 2000,
            'car': 120
        }
        params.additional_service_costs = {
            'packing': {
                'studio': 100,
                '1-bedroom': 150,
                '2-bedroom': 200,
                '3-bedroom': 250,
                '4-bedroom': 300,
                'office': 350,
                'car': 50
            },
            'storage': {
                'studio': 80,
                '1-bedroom': 130,
                '2-bedroom': 180,
                '3-bedroom': 230,
                '4-bedroom': 280,
                'office': 300,
                'car': 50
            }
        }
        params.rate_adjustments = {
            'seasonality_rate': 0.10,
            'rural_location_rate': 0.10,
            'max_cost_multiplier': 1.2,
            'min_cost_multiplier': 0.8
        }
        params.email_config = {
            "email_notifications": True,
            "staff_email_subject": "New Moving Request",
            "customer_email_template": "Dear {{customer_name}},\n\nThank you for your moving request from {{origin}} to {{destination}} on {{move_date}}.\n\nYour estimated cost is ${{total_cost}}.\n\nRegards,\nThe Moving Team",
            "staff_email_template": "New moving request:\n- Customer: {{customer_name}}\n- From: {{origin}}\n- To: {{destination}}\n- Date: {{move_date}}\n- Size: {{move_size}}\n- Estimated cost: ${{total_cost}}"
        }
        
        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Parameters reset successfully',
                'moving_parameters': {
                    'base_rate_per_mile': params.base_rate_per_mile,
                    'move_size_rates': params.move_size_rates,
                    'additional_service_costs': params.additional_service_costs,
                    'rate_adjustments': params.rate_adjustments,
                    'email_config': params.email_config
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Error resetting parameters: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/calculate-moving-cost', methods=['POST'])
def calculate_moving_cost():
    """
    Calculate moving cost for a specific company
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get company ID from user's company
        company_id = user.company_id or user.id
        
        # Get moving parameters
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        if not params:
            return jsonify({
                'success': False,
                'error': 'Moving parameters not found'
            }), 404
        
        # Calculate base cost
        distance = float(data.get('distance', 0))
        move_size = data.get('move_size', 'studio')
        base_cost = params.move_size_rates.get(move_size, 0)
        
        # Add distance cost
        distance_cost = distance * params.base_rate_per_mile
        
        # Calculate total cost
        total_cost = base_cost + distance_cost
        
        # Apply min/max cost multipliers
        min_multiplier = params.rate_adjustments.get('min_cost_multiplier', 0.8)
        max_multiplier = params.rate_adjustments.get('max_cost_multiplier', 1.2)
        min_cost = total_cost * min_multiplier
        max_cost = total_cost * max_multiplier
        
        return jsonify({
            'success': True,
            'estimate': {
                'base_cost': base_cost,
                'distance_cost': distance_cost,
                'min_cost': min_cost,
                'max_cost': max_cost
            }
        })
        
    except Exception as e:
        logger.error(f"Error calculating moving cost: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/submit-moving-quote', methods=['POST'])
def submit_moving_quote():
    """
    Submit a moving quote request
    """
    try:
        # Get request data
        data = request.get_json()
        logger.info(f"Received submit-moving-quote request with data: {data}")
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get company ID from request data or user's company
        company_id = data.get('company_id') or user.company_id or user.id
        
        # Check if user has access to the requested company
        user_company_id = user.company_id or user.id
        
        # Allow access if user is admin or belongs to the company
        is_admin = False
        try:
            from admin.models import AdminUser
            is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
        except:
            pass
            
        if not is_admin and user_company_id != company_id:
            return jsonify({
                'success': False,
                'error': 'You do not have access to this company'
            }), 403
        
        # Ensure the company exists in our database
        company = Company.query.get(company_id)
        if not company:
            logger.warning(f"Company {company_id} not found; creating minimal record.")
            company = Company(
                id=company_id,
                name=f"Company {company_id}",
                email=f"company_{company_id}@no-reply.local"
            )
            db.session.add(company)
            db.session.commit()

        # Create moving quote request
        quote = MovingQuoteRequest(
            company_id=company_id,
            origin=data.get('origin'),
            destination=data.get('destination'),
            distance_miles=float(data.get('distance_miles', 0)),
            move_size=data.get('move_size'),
            move_date=datetime.strptime(data.get('move_date'), '%Y-%m-%d').date(),
            customer_name=data.get('customer_name'),
            customer_email=data.get('customer_email'),
            customer_phone=data.get('customer_phone'),
            recipient_email=data.get('recipient_email', data.get('customer_email')),
            total_cost=float(data.get('total_cost', 0)),
            additional_services=data.get('additional_services', {}),
            notes=data.get('notes', '')
        )
        
        try:
            db.session.add(quote)
            db.session.commit()
            
            # Send email notifications if configured
            params = MovingParameters.query.filter_by(company_id=company_id).first()
            if params and params.email_config and params.email_config.get('email_notifications', False):
                try:
                    from services.email_service import EmailService
                    email_service = EmailService()
                    
                    # Send customer email
                    customer_template = params.email_config.get('customer_email_template', '')
                    if customer_template:
                        customer_data = {
                            'customer_name': quote.customer_name,
                            'origin': quote.origin,
                            'destination': quote.destination,
                            'move_date': quote.move_date.strftime('%Y-%m-%d'),
                            'total_cost': f"{quote.total_cost:.2f}"
                        }
                        customer_email = email_service.apply_template(customer_template, customer_data)
                        email_service.send_email(
                            to_email=quote.customer_email,
                            subject='Your Moving Quote',
                            body=customer_email
                        )
                    
                    # Send staff email
                    staff_template = params.email_config.get('staff_email_template', '')
                    if staff_template:
                        staff_data = {
                            'customer_name': quote.customer_name,
                            'origin': quote.origin,
                            'destination': quote.destination,
                            'move_date': quote.move_date.strftime('%Y-%m-%d'),
                            'move_size': quote.move_size,
                            'total_cost': f"{quote.total_cost:.2f}"
                        }
                        staff_email = email_service.apply_template(staff_template, staff_data)
                        email_service.send_email(
                            to_email=params.email_config.get('staff_email', ''),
                            subject=params.email_config.get('staff_email_subject', 'New Moving Quote'),
                            body=staff_email
                        )
                except Exception as e:
                    logger.error(f"Error sending email notifications: {str(e)}")
            
            return jsonify({
                'success': True,
                'message': 'Moving quote submitted successfully',
                'quote_id': quote.id
            })
            
        except Exception as e:
            db.session.rollback()
            logger.exception("Error in submit-moving-quote")
            return jsonify({
                'success': False,
                'error': f'Error submitting quote: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.exception("Error in submit-moving-quote")
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/send-estimate-email', methods=['POST'])
def send_estimate_email():
    try:
        data = request.get_json()
        if not data:
            logger.error("No data provided in request")
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Log the request data to help debug
        logger.info(f"Received send-estimate-email request with data: {data}")
        
        # Debug customer information fields
        customer_name = data.get('customer_name', 'Not provided')
        customer_email = data.get('customer_email', 'Not provided')
        customer_phone = data.get('customer_phone', 'Not provided')
        
        logger.info(f"Customer information: Name={customer_name}, Email={customer_email}, Phone={customer_phone}")

        # Get staff email from request data
        staff_email = data.get('staff_email')
        if not staff_email:
            logger.error("Staff email not provided")
            return jsonify({
                'success': False,
                'error': 'Staff email not provided'
            }), 400

        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", staff_email):
            logger.error(f"Invalid staff email format: {staff_email}")
            return jsonify({
                'success': False,
                'error': 'Invalid staff email format'
            }), 400

        # Get SMTP configuration from request data
        smtp_config = data.get('smtp_config', {
            "server": "smtp.gmail.com",
            "port": 587,
            "username": "info@movergpt.com",
            "password": "squx iyum vgaw yqhv"
        })
        
        # Log SMTP config (without password)
        safe_smtp_config = {k: v for k, v in smtp_config.items() if k != 'password'}
        safe_smtp_config['password'] = '********'
        logger.info(f"Using SMTP config: {safe_smtp_config}")
        
        # Create HTML email content for customer
        customer_email_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4361ee; color: white; padding: 10px 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                .total {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Your Moving Cost Estimate</h2>
                </div>
                <div class="content">
                    <p>Hello {data.get('customer_name', 'Valued Customer')},</p>
                    <p>Thank you for requesting a moving cost estimate. Below are the details of your request:</p>
                    
                    <h3>Moving Details:</h3>
                    <table>
                        <tr>
                            <th>From:</th>
                            <td>{data.get('origin', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>To:</th>
                            <td>{data.get('destination', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Move Date:</th>
                            <td>{data.get('move_date', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Move Size:</th>
                            <td>{data.get('move_size', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Distance:</th>
                            <td>{data.get('distance', 'N/A')} miles</td>
                        </tr>
                    </table>
                    
                    <h3>Cost Breakdown:</h3>
                    <table>
                        <tr>
                            <th>Base Rate:</th>
                            <td>${float(data.get('estimate', {}).get('base_cost', 0.0)):.2f}</td>
                        </tr>
                        <tr>
                            <th>Distance Cost:</th>
                            <td>${float(data.get('estimate', {}).get('distance_cost', 0.0)):.2f}</td>
                        </tr>
                        {f"<tr><th>Packing Service:</th><td>${float(data.get('estimate', {}).get('packing_cost', 0.0)):.2f}</td></tr>" if data.get('estimate', {}).get('packing_cost') else ""}
                        {f"<tr><th>Storage Service:</th><td>${float(data.get('estimate', {}).get('storage_cost', 0.0)):.2f}</td></tr>" if data.get('estimate', {}).get('storage_cost') else ""}
                        <tr class="total">
                            <th>Estimated Total:</th>
                            <td>${float(data.get('estimate', {}).get('min_cost', 0.0)):.2f} - ${float(data.get('estimate', {}).get('max_cost', 0.0)):.2f}</td>
                        </tr>
                    </table>
                    
                    <p>Please note that this is an estimate, and the final cost may vary based on actual moving conditions and services required.</p>
                    
                    <p>If you have any questions or would like to book your move, please contact us:</p>
                    <ul>
                        <li>Phone: 555-123-4567</li>
                        <li>Email: info@movergpt.com</li>
                    </ul>
                    
                    <p>Thank you for choosing our service!</p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Create HTML email content for staff
        staff_email_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4361ee; color: white; padding: 10px 20px; text-align: center; }}
                .highlight {{ background-color: #fffde7; padding: 15px; border-left: 4px solid #ffd600; margin: 15px 0; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                .total {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>New Moving Quote Request</h2>
                </div>
                <div class="content">
                    <div class="highlight">
                        <h3>Customer Information:</h3>
                        <table>
                            <tr>
                                <th>Name:</th>
                                <td><strong>{data.get('customer_name', 'N/A')}</strong></td>
                            </tr>
                            <tr>
                                <th>Email:</th>
                                <td><strong>{data.get('customer_email', 'N/A')}</strong></td>
                            </tr>
                            <tr>
                                <th>Phone:</th>
                                <td><strong>{data.get('customer_phone', 'N/A')}</strong></td>
                            </tr>
                        </table>
                    </div>
                    
                    <h3>Moving Details:</h3>
                    <table>
                        <tr>
                            <th>From:</th>
                            <td>{data.get('origin', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>To:</th>
                            <td>{data.get('destination', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Move Date:</th>
                            <td>{data.get('move_date', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Move Size:</th>
                            <td>{data.get('move_size', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Distance:</th>
                            <td>{data.get('distance', 'N/A')} miles</td>
                        </tr>
                    </table>
                    
                    <h3>Cost Breakdown:</h3>
                    <table>
                        <tr>
                            <th>Base Rate:</th>
                            <td>${float(data.get('estimate', {}).get('base_cost', 0.0)):.2f}</td>
                        </tr>
                        <tr>
                            <th>Distance Cost:</th>
                            <td>${float(data.get('estimate', {}).get('distance_cost', 0.0)):.2f}</td>
                        </tr>
                        {f"<tr><th>Packing Service:</th><td>${float(data.get('estimate', {}).get('packing_cost', 0.0)):.2f}</td></tr>" if data.get('estimate', {}).get('packing_cost') else ""}
                        {f"<tr><th>Storage Service:</th><td>${float(data.get('estimate', {}).get('storage_cost', 0.0)):.2f}</td></tr>" if data.get('estimate', {}).get('storage_cost') else ""}
                        <tr class="total">
                            <th>Estimated Total:</th>
                            <td>${float(data.get('estimate', {}).get('min_cost', 0.0)):.2f} - ${float(data.get('estimate', {}).get('max_cost', 0.0)):.2f}</td>
                        </tr>
                    </table>
                    
                    <p>This is a new quote request received from your moving cost calculator.</p>
                    <p><strong>Action required:</strong> Please contact the customer as soon as possible to confirm the booking.</p>
                </div>
                <div class="footer">
                    <p>This is an automated email from MoverGPT. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send the emails
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            # Initialize email service - direct implementation for better debugging
            server = smtplib.SMTP(smtp_config["server"], smtp_config["port"])
            server.starttls()
            
            try:
                # Log in to the server
                logger.info(f"Attempting to login with username: {smtp_config['username']}")
                server.login(smtp_config["username"], smtp_config["password"])
                logger.info("SMTP login successful")
                
                # Function to send an email
                def send_direct_email(to_email, subject, html_body):
                    logger.info(f"Preparing to send email to: {to_email}")
                    
                    message = MIMEMultipart("alternative")
                    message["Subject"] = subject
                    message["From"] = smtp_config["username"]
                    message["To"] = to_email
                    
                    # Create HTML part
                    html_part = MIMEText(html_body, "html")
                    message.attach(html_part)
                    
                    # Send email
                    server.sendmail(
                        smtp_config["username"],
                        to_email,
                        message.as_string()
                    )
                    logger.info(f"Email sent successfully to {to_email}")
                    return True, "Email sent successfully"
                
                # Send customer email if this is not just a staff test
                if data.get('customer_email') and not data.get('is_test_only'):
                    logger.info("Attempting to send customer email")
                    customer_success, customer_message = send_direct_email(
                        data.get('customer_email'),
                        "Your Moving Cost Estimate",
                        customer_email_html
                    )
                    
                    if not customer_success:
                        logger.error(f"Failed to send customer email: {customer_message}")
                        return jsonify({
                            'success': False,
                            'error': f'Failed to send customer email: {customer_message}'
                        }), 500
                
                # Always send staff email
                logger.info(f"Attempting to send staff email to {staff_email}")
                staff_success, staff_message = send_direct_email(
                    staff_email,
                    f"New Moving Quote Request from {data.get('customer_name', 'Customer')}",
                    staff_email_html
                )
                
                if not staff_success:
                    logger.error(f"Failed to send staff email: {staff_message}")
                    return jsonify({
                        'success': False,
                        'error': f'Failed to send staff email: {staff_message}'
                    }), 500
                
                logger.info("All emails sent successfully")
                return jsonify({
                    'success': True,
                    'message': 'Estimate emails sent successfully',
                    'email_sent': True
                })
                    
            finally:
                # Close the connection to the server
                try:
                    server.quit()
                    logger.info("SMTP connection closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing SMTP connection: {str(e)}")
                
        except Exception as e:
            error_message = f"Error sending emails: {str(e)}"
            logger.error(error_message)
            return jsonify({
                'success': False,
                'error': error_message
            }), 500
            
    except Exception as e:
        error_message = f"Error processing request: {str(e)}"
        logger.error(error_message)
        return jsonify({
            'success': False,
            'error': error_message
        }), 500

@companies_bp.route('/test-estimate-email', methods=['GET'])
def test_estimate_email():
    """
    Test endpoint to send a sample estimate email
    """
    try:
        # Get email from query parameter
        recipient_email = request.args.get('email')
        if not recipient_email:
            return jsonify({
                'success': False,
                'error': 'Email parameter is required'
            }), 400
            
        # Create sample data for testing
        sample_data = {
            'customer_name': 'Test Customer',
            'origin': '123 Main St, New York, NY',
            'destination': '456 Oak Ave, Los Angeles, CA',
            'move_date': '2024-07-15',
            'move_size': '2-bedroom',
            'distance': 2800,
            'recipient_email': recipient_email
        }
        
        # Create sample estimate
        sample_estimate = {
            'base_cost': 500,
            'distance_cost': 1680.00,
            'packing_cost': 350.00,
            'storage_cost': None,
            'min_cost': 2400.00,
            'max_cost': 2700.00
        }
        
        # Create HTML email content
        email_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4361ee; color: white; padding: 10px 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                .total {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Your Moving Cost Estimate</h2>
                </div>
                <div class="content">
                    <p>Hello {sample_data.get('customer_name', 'Valued Customer')},</p>
                    <p>Thank you for requesting a moving cost estimate. Below are the details of your request:</p>
                    
                    <h3>Moving Details:</h3>
                    <table>
                        <tr>
                            <th>From:</th>
                            <td>{sample_data.get('origin', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>To:</th>
                            <td>{sample_data.get('destination', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Move Date:</th>
                            <td>{sample_data.get('move_date', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Move Size:</th>
                            <td>{sample_data.get('move_size', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>Distance:</th>
                            <td>{sample_data.get('distance', 'N/A')} miles</td>
                        </tr>
                    </table>
                    
                    <h3>Cost Breakdown:</h3>
                    <table>
                        <tr>
                            <th>Base Rate:</th>
                            <td>${float(sample_estimate.get('base_cost', 0.0)):.2f}</td>
                        </tr>
                        <tr>
                            <th>Distance Cost:</th>
                            <td>${float(sample_estimate.get('distance_cost', 0.0)):.2f}</td>
                        </tr>
                        {f"<tr><th>Packing Service:</th><td>${float(sample_estimate.get('packing_cost', 0.0)):.2f}</td></tr>" if sample_estimate.get('packing_cost') else ""}
                        {f"<tr><th>Storage Service:</th><td>${float(sample_estimate.get('storage_cost', 0.0)):.2f}</td></tr>" if sample_estimate.get('storage_cost') else ""}
                        <tr class="total">
                            <th>Estimated Total:</th>
                            <td>${float(sample_estimate.get('min_cost', 0.0)):.2f} - ${float(sample_estimate.get('max_cost', 0.0)):.2f}</td>
                        </tr>
                    </table>
                    
                    <p>Please note that this is an estimate, and the final cost may vary based on actual moving conditions and services required.</p>
                    
                    <p>If you have any questions or would like to book your move, please contact us:</p>
                    <ul>
                        <li>Phone: 555-123-4567</li>
                        <li>Email: info@movergpt.com</li>
                    </ul>
                    
                    <p>Thank you for choosing our service!</p>
                    
                    <p><strong>This is a test email sent from the test endpoint.</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Set up SMTP configuration
        smtp_config = {
            "server": "smtp.gmail.com",
            "port": 587,
            "username": "info@movergpt.com",
            "password": "squx iyum vgaw yqhv"  # Using the provided app password
        }
        
        # Send the email
        from services.email_service import EmailService
        
        # Initialize email service
        email_service = EmailService(smtp_config)
        
        # Send email
        success, message = email_service.send_email(
            to_email=recipient_email,
            subject="[TEST] Your Moving Cost Estimate",
            body=email_html
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Test estimate email sent successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to send test email: {message}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/moving-quote-requests', methods=['GET'], endpoint='dashboard_moving_quote_requests')
def get_dashboard_moving_quote_requests():
    """
    Get moving quote requests for the authenticated company
    """
    try:
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get company ID from user's company
        company_id = user.company_id or user.id
        
        # Get query parameters
        limit = request.args.get('limit', 10, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Get quote requests
        quotes = MovingQuoteRequest.query.filter_by(company_id=company_id).order_by(MovingQuoteRequest.created_at.desc()).limit(limit).offset(offset).all()
        
        # Get total count
        total_count = MovingQuoteRequest.query.filter_by(company_id=company_id).count()
        
        return jsonify({
            'success': True,
            'quotes': [{
                'id': quote.id,
                'origin': quote.origin,
                'destination': quote.destination,
                'distance_miles': quote.distance_miles,
                'move_size': quote.move_size,
                'move_date': quote.move_date.strftime('%Y-%m-%d'),
                'customer_name': quote.customer_name,
                'customer_email': quote.customer_email,
                'customer_phone': quote.customer_phone,
                'total_cost': quote.total_cost,
                'additional_services': quote.additional_services,
                'notes': quote.notes,
                'status': quote.status,
                'created_at': quote.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for quote in quotes],
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/debug/moving-parameters/<int:company_id>', methods=['GET'])
def debug_get_moving_parameters(company_id):
    """
    Debug endpoint to get moving parameters for a company
    """
    try:
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get company ID from user's company
        user_company_id = user.company_id or user.id
        
        # Allow access if user is admin or belongs to the company
        is_admin = False
        try:
            from admin.models import AdminUser
            is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
        except:
            pass
            
        if not is_admin and user_company_id != company_id:
            return jsonify({
                'success': False,
                'error': 'You do not have access to this company'
            }), 403
        
        # Get moving parameters
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        if not params:
            return jsonify({
                'success': False,
                'error': 'Moving parameters not found'
            }), 404
        
        return jsonify({
            'success': True,
            'moving_parameters': {
                'base_rate_per_mile': params.base_rate_per_mile,
                'move_size_rates': params.move_size_rates,
                'additional_service_costs': params.additional_service_costs,
                'rate_adjustments': params.rate_adjustments,
                'email_config': params.email_config
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/debug/auth-check', methods=['GET'])
def debug_auth_check():
    """
    Debug endpoint to check authentication status
    """
    try:
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get company ID from user's company
        company_id = user.company_id or user.id
        
        return jsonify({
            'success': True,
            'user_id': user.id,
            'company_id': company_id,
            'is_admin': current_user.is_authenticated and isinstance(current_user, AdminUser)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/debug/create-moving-parameters', methods=['POST'])
def debug_create_moving_parameters():
    """
    Debug endpoint to create moving parameters for a company
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get company ID from request data
        company_id = data.get('company_id')
        if not company_id:
            return jsonify({
                'success': False,
                'error': 'Company ID is required'
            }), 400
        
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get company ID from user's company
        user_company_id = user.company_id or user.id
        
        # Allow access if user is admin or belongs to the company
        is_admin = False
        try:
            from admin.models import AdminUser
            is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
        except:
            pass
            
        if not is_admin and user_company_id != int(company_id):
            return jsonify({
                'success': False,
                'error': 'You do not have access to this company'
            }), 403
        
        # Create moving parameters
        params = MovingParameters(
            company_id=company_id,
            base_rate_per_mile=data.get('base_rate_per_mile', 1.50),
            move_size_rates=data.get('move_size_rates', {
                'studio': 320,
                '1-bedroom': 640,
                '2-bedroom': 960,
                '3-bedroom': 1280,
                '4-bedroom': 1600,
                'office': 2000,
                'car': 120
            }),
            additional_service_costs=data.get('additional_service_costs', {
                'packing': {
                    'studio': 100,
                    '1-bedroom': 150,
                    '2-bedroom': 200,
                    '3-bedroom': 250,
                    '4-bedroom': 300,
                    'office': 350,
                    'car': 50
                },
                'storage': {
                    'studio': 80,
                    '1-bedroom': 130,
                    '2-bedroom': 180,
                    '3-bedroom': 230,
                    '4-bedroom': 280,
                    'office': 300,
                    'car': 50
                }
            }),
            rate_adjustments=data.get('rate_adjustments', {
                'seasonality_rate': 0.10,
                'rural_location_rate': 0.10,
                'max_cost_multiplier': 1.2,
                'min_cost_multiplier': 0.8
            }),
            email_config=data.get('email_config', {
                'email_notifications': True,
                'staff_email_subject': 'New Moving Request',
                'customer_email_template': 'Dear {{customer_name}},\n\nThank you for your moving request from {{origin}} to {{destination}} on {{move_date}}.\n\nYour estimated cost is ${{total_cost}}.\n\nRegards,\nThe Moving Team',
                'staff_email_template': 'New moving request:\n- Customer: {{customer_name}}\n- From: {{origin}}\n- To: {{destination}}\n- Date: {{move_date}}\n- Size: {{move_size}}\n- Estimated cost: ${{total_cost}}'
            })
        )
        
        try:
            db.session.add(params)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Moving parameters created successfully',
                'moving_parameters': {
                    'base_rate_per_mile': params.base_rate_per_mile,
                    'move_size_rates': params.move_size_rates,
                    'additional_service_costs': params.additional_service_costs,
                    'rate_adjustments': params.rate_adjustments,
                    'email_config': params.email_config
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Error creating parameters: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/<int:company_id>/test-email', methods=['POST'])
def test_moving_parameters_email(company_id):
    """
    Test email notifications for a company
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Check if user has access to the requested company
        user_company_id = user.company_id or user.id
        
        # Allow access if user is admin or belongs to the company
        is_admin = False
        try:
            from admin.models import AdminUser
            is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
        except:
            pass
            
        if not is_admin and user_company_id != company_id:
            return jsonify({
                'success': False,
                'error': 'You do not have access to this company'
            }), 403
        
        # Get moving parameters
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        if not params:
            return jsonify({
                'success': False,
                'error': 'Moving parameters not found'
            }), 404
        
        # Send test email
        try:
            # Initialize email service with SMTP settings
            smtp_cfg = params.email_config.get('smtp', {})
            email_service = EmailService(smtp_cfg)
            
            # Send customer email
            customer_template = params.email_config.get('customer_email_template', '')
            if customer_template:
                customer_data = {
                    'customer_name': data.get('customer_name', 'Test Customer'),
                    'origin': data.get('origin', 'Test Origin'),
                    'destination': data.get('destination', 'Test Destination'),
                    'move_date': data.get('move_date', '2024-01-01'),
                    'total_cost': f"{data.get('total_cost', 1000):.2f}"
                }
                customer_email = apply_template(customer_template, customer_data)
                email_service.send_email(
                    to_email=data.get('customer_email', 'test@example.com'),
                    subject='Test Moving Quote',
                    body=customer_email
                )
            
            # Send staff email
            staff_template = params.email_config.get('staff_email_template', '')
            if staff_template:
                staff_data = {
                    'customer_name': data.get('customer_name', 'Test Customer'),
                    'origin': data.get('origin', 'Test Origin'),
                    'destination': data.get('destination', 'Test Destination'),
                    'move_date': data.get('move_date', '2024-01-01'),
                    'move_size': data.get('move_size', 'studio'),
                    'total_cost': f"{data.get('total_cost', 1000):.2f}"
                }
                staff_email = apply_template(staff_template, staff_data)
                email_service.send_email(
                    to_email=params.email_config.get('staff_email', 'staff@example.com'),
                    subject=params.email_config.get('staff_email_subject', 'Test Moving Quote'),
                    body=staff_email
                )
            
            return jsonify({
                'success': True,
                'message': 'Test emails sent successfully'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Error sending test emails: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/get-distance', methods=['POST'])
def get_distance():
    """
    Get distance between two locations
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get origin and destination
        origin = data.get('origin')
        destination = data.get('destination')
        
        if not origin or not destination:
            return jsonify({
                'success': False,
                'error': 'Origin and destination are required'
            }), 400
        
        # Use Google Maps Distance Matrix API or fallback
        try:
            from utils.google_maps_utils import get_distance_between_locations
            
            # Get distance using the utility function which handles fallback
            distance_data = get_distance_between_locations(origin, destination)
            
            return jsonify({
                'success': True,
                'distance': {
                    'miles': distance_data['distance_miles'],
                    'status': distance_data['status']
                }
            })
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Error getting distance: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500

@companies_bp.route('/calculate-moving-cost-with-lookup', methods=['POST'])
def calculate_moving_cost_with_lookup():
    """
    Calculate moving cost with distance lookup
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get token from request
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Verify the token
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get company ID from user data
        from users.models import User
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get company ID from user's company
        company_id = user.company_id or user.id
        
        # Get origin and destination
        origin = data.get('origin')
        destination = data.get('destination')
        
        if not origin or not destination:
            return jsonify({
                'success': False,
                'error': 'Origin and destination are required'
            }), 400
        
        # Get distance
        try:
            import requests
            from core.config import Config
            
            api_key = Config.GOOGLE_MAPS_API_KEY
            url = f'https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin}&destinations={destination}&key={api_key}'
            
            response = requests.get(url)
            result = response.json()
            
            if result['status'] == 'OK':
                distance = result['rows'][0]['elements'][0]['distance']['value'] / 1609.34  # Convert meters to miles
            else:
                return jsonify({
                    'success': False,
                    'error': f'Error getting distance: {result["status"]}'
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Error getting distance: {str(e)}'
            }), 500
        
        # Get moving parameters
        params = MovingParameters.query.filter_by(company_id=company_id).first()
        if not params:
            return jsonify({
                'success': False,
                'error': 'Moving parameters not found'
            }), 404
        
        # Calculate base cost
        move_size = data.get('move_size', 'studio')
        base_cost = params.move_size_rates.get(move_size, 0)
        
        # Add distance cost
        distance_cost = distance * params.base_rate_per_mile
        
        # Add additional services
        additional_services = data.get('additional_services', [])
        service_cost = 0
        for service in additional_services:
            service_cost += params.additional_service_costs.get(service, {}).get(move_size, 0)
        
        # Calculate total cost
        total_cost = base_cost + distance_cost + service_cost
        
        # Apply rate adjustments
        if data.get('is_rural', False):
            total_cost *= (1 + params.rate_adjustments.get('rural_location_rate', 0))
        
        if data.get('is_seasonal', False):
            total_cost *= (1 + params.rate_adjustments.get('seasonality_rate', 0))
        
        # Apply min/max cost multipliers
        min_multiplier = params.rate_adjustments.get('min_cost_multiplier', 0.8)
        max_multiplier = params.rate_adjustments.get('max_cost_multiplier', 1.2)
        total_cost = max(total_cost * min_multiplier, min(total_cost * max_multiplier, total_cost))
        
        return jsonify({
            'success': True,
            'cost_breakdown': {
                'base_cost': base_cost,
                'distance_cost': distance_cost,
                'service_cost': service_cost,
                'total_cost': total_cost
            },
            'distance_miles': round(distance, 2)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error occurred: {str(e)}'
        }), 500 