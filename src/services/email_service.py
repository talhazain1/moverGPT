import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os
from typing import Dict, Any, Optional, Tuple
import traceback

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails using SMTP."""
    
    def __init__(self, smtp_config: Dict[str, Any]):
        """
        Initialize the email service with SMTP configuration.
        
        Args:
            smtp_config: Dictionary containing SMTP configuration:
                server: SMTP server address
                port: SMTP server port
                username: SMTP username (email)
                password: SMTP password
        """
        self.smtp_config = smtp_config
        self.server = smtp_config.get('server')
        self.port = int(smtp_config.get('port', 587))
        self.username = smtp_config.get('username')
        self.password = smtp_config.get('password')
        
        # Log SMTP configuration (excluding password)
        logger_config = smtp_config.copy()
        if 'password' in logger_config:
            logger_config['password'] = '********'  # Hide the actual password
        logger.info(f"EmailService initialized with config: {logger_config}")
    
    def send_email(self, to_email: str, subject: str, body: str) -> Tuple[bool, str]:
        """
        Send an email using the configured SMTP server.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content (HTML or plain text)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate parameters
            if not self.server or not self.username or not self.password:
                error_msg = "Missing SMTP configuration (server, username, or password)"
                logger.error(error_msg)
                return False, error_msg
                
            if not to_email:
                error_msg = "Recipient email address is missing"
                logger.error(error_msg)
                return False, error_msg
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = to_email
            
            # Attach the body as both plain text and HTML
            part1 = MIMEText(body, 'plain')
            part2 = MIMEText(body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Connect to SMTP server with detailed logging
            logger.info(f"Connecting to SMTP server {self.server}:{self.port}")
            try:
                smtp = smtplib.SMTP(self.server, self.port)
                smtp.set_debuglevel(1)  # Enable debug output
                logger.info("SMTP connection established")
            except Exception as conn_error:
                error_msg = f"Failed to connect to SMTP server: {str(conn_error)}"
                logger.error(error_msg)
                return False, error_msg
            
            # Start TLS for security
            try:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                logger.info("STARTTLS successful")
            except Exception as tls_error:
                error_msg = f"Failed during STARTTLS: {str(tls_error)}"
                logger.error(error_msg)
                smtp.quit()
                return False, error_msg
            
            # Login to SMTP server
            try:
                logger.info(f"Logging in as {self.username}")
                smtp.login(self.username, self.password)
                logger.info("SMTP login successful")
            except smtplib.SMTPAuthenticationError as auth_error:
                error_msg = "SMTP authentication failed. Check username and password."
                logger.error(f"{error_msg}: {str(auth_error)}")
                smtp.quit()
                return False, error_msg
            except Exception as login_error:
                error_msg = f"Login error: {str(login_error)}"
                logger.error(error_msg)
                smtp.quit()
                return False, error_msg
            
            # Send email
            try:
                logger.info(f"Sending email to {to_email} with subject: {subject}")
                smtp.sendmail(self.username, to_email, msg.as_string())
                logger.info(f"Email sent successfully to {to_email}")
            except Exception as send_error:
                error_msg = f"Failed to send email: {str(send_error)}"
                logger.error(error_msg)
                smtp.quit()
                return False, error_msg
            
            # Close connection
            smtp.quit()
            logger.info("SMTP connection closed")
            
            return True, "Email sent successfully"
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False, error_msg
    
    def send_emails(self, staff_email: Dict[str, str], customer_email: Dict[str, str]) -> Dict[str, Any]:
        """
        Send emails to both staff and customer.
        
        Args:
            staff_email: Dictionary with staff email details:
                to: Staff email address
                subject: Email subject
                body: Email body
            customer_email: Dictionary with customer email details:
                to: Customer email address
                subject: Email subject
                body: Email body
                
        Returns:
            Dictionary with results for both emails
        """
        results = {
            "success": False,
            "staff_email": {},
            "customer_email": {}
        }
        
        # Log the email details
        logger.info(f"Sending staff email to: {staff_email.get('to')}")
        logger.info(f"Staff email subject: {staff_email.get('subject')}")
        logger.info(f"Staff email body (first 100 chars): {staff_email.get('body', '')[:100]}...")
        
        logger.info(f"Sending customer email to: {customer_email.get('to')}")
        logger.info(f"Customer email subject: {customer_email.get('subject')}")
        logger.info(f"Customer email body (first 100 chars): {customer_email.get('body', '')[:100]}...")
        
        # Send staff email
        staff_success, staff_message = self.send_email(
            staff_email['to'], 
            staff_email['subject'], 
            staff_email['body']
        )
        results["staff_email"] = {
            "success": staff_success,
            "message": staff_message
        }
        
        # Send customer email
        customer_success, customer_message = self.send_email(
            customer_email['to'], 
            customer_email['subject'], 
            customer_email['body']
        )
        results["customer_email"] = {
            "success": customer_success,
            "message": customer_message
        }
        
        # Overall success is true only if both emails were sent successfully
        results["success"] = staff_success and customer_success
        
        # Log the results
        logger.info(f"Email sending results: Staff: {staff_success}, Customer: {customer_success}")
        
        return results


def apply_template(template: str, data: Dict[str, Any]) -> str:
    """
    Apply data values to template placeholders.
    
    Args:
        template: String template with placeholders like {{key}}
        data: Dictionary of data to insert into placeholders
        
    Returns:
        Processed template with values inserted
    """
    if not template:
        return ""
        
    result = template
    for key, value in data.items():
        placeholder = f"{{{{{key}}}}}"
        if value is None:
            value = ""
        result = result.replace(placeholder, str(value))
    
    return result 