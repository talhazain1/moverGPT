from flask import Blueprint, request, jsonify
from services.email_service import EmailService, apply_template
from flask_login import login_required
import logging
from core.database import db
from users.models import User
from companies.models import Company

logger = logging.getLogger(__name__)
email_bp = Blueprint('email', __name__)

@email_bp.route('/send', methods=['POST'])
def send_email():
    """
    API endpoint to send emails to staff and customers.
    
    Expected JSON request body:
    {
        "smtp": {
            "server": "smtp.gmail.com",
            "port": 587,
            "username": "info@movergpt.com",
            "password": "app_password",
            "staff_email": "staff@example.com"
        },
        "staff_email": {
            "to": "staff@example.com",
            "subject": "New Moving Request from {{customer_name}}",
            "body": "Staff email body with {{placeholders}}"
        },
        "customer_email": {
            "to": "customer@example.com",
            "subject": "Your Moving Quote",
            "body": "Customer email body with {{placeholders}}"
        },
        "is_test": true  // Optional flag for test emails
    }
    
    Returns:
    {
        "success": true,
        "staff_email": {
            "success": true,
            "message": "Email sent successfully"
        },
        "customer_email": {
            "success": true,
            "message": "Email sent successfully"
        }
    }
    """
    try:
        # Get request data
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Missing request data"}), 400
        
        # Validate required data
        smtp_config = data.get('smtp')
        staff_email_data = data.get('staff_email')
        customer_email_data = data.get('customer_email')
        
        if not smtp_config or not staff_email_data or not customer_email_data:
            return jsonify({
                "success": False, 
                "error": "Missing required SMTP configuration or email data"
            }), 400
        
        # Create email service
        email_service = EmailService(smtp_config)
        
        # Check if this is a test email
        is_test = data.get('is_test', False)
        if is_test:
            logger.info("Sending test emails")
        
        # Send emails
        result = email_service.send_emails(staff_email_data, customer_email_data)
        
        # Return results
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@email_bp.route('/templates', methods=['GET'])
def get_default_templates():
    """Get default email templates for staff and customer emails."""
    default_templates = {
        "staff_email_subject": "New Moving Request from {{customer_name}}",
        "staff_email_template": """
        New Moving Request

        Customer Information:
        - Name: {{customer_name}}
        - Email: {{customer_email}}
        - Phone: {{customer_phone}}

        Moving Details:
        - From: {{origin}}
        - To: {{destination}}
        - Moving Date: {{move_date}}
        - Move Size: {{move_size}}
        - Distance: {{distance}} miles
        - Additional Services: {{additional_services}}

        Cost Breakdown:
        - Base Rate: ${{base_rate}}
        - Distance Cost: ${{distance_cost}}
        - Services Cost: ${{services_cost}}
        - Adjustments: ${{adjustments}}
        - Total Cost: ${{total_cost}}

        Notes: {{notes}}

        Please contact the customer as soon as possible to confirm the booking.
        """,
        "customer_email_template": """
        Dear {{customer_name}}, 

        Thank you for requesting a moving quote with My Moving Journey! Here are the details of your request: 
        - From: {{origin}} 
        - To: {{destination}} 
        - Moving Date: {{move_date}} 
        - Move Size: {{move_size}} 
        - Additional Services: {{additional_services}}

        Your estimated cost is ${{total_cost}}. 
        We will contact you shortly to confirm your booking. 
        If you have any questions, please reply to this email or call us. 
        Thank you for choosing My Moving Journey! 

        Best regards, 
        The Moving Team
        
        """
    }
    
    return jsonify({
        "success": True,
        "templates": default_templates
    })

@email_bp.route('/preview', methods=['POST'])
def preview_email():
    """
    Preview an email with sample data applied to templates.
    
    Expected JSON request body:
    {
        "template": "Email template with {{placeholders}}",
        "data": {
            "placeholder1": "value1",
            "placeholder2": "value2"
        }
    }
    
    Returns:
    {
        "success": true,
        "preview": "Email template with value1"
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Missing request data"}), 400
        
        template = data.get('template')
        template_data = data.get('data', {})
        
        if not template:
            return jsonify({"success": False, "error": "Missing template"}), 400
        
        preview = apply_template(template, template_data)
        
        return jsonify({
            "success": True,
            "preview": preview
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500 