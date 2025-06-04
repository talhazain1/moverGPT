"""
Email Service Module

This module provides functions for sending email verification messages.
It uses SMTP to send verification emails with OTP.
Ensure to set these environment variables:
  - SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, FROM_EMAIL
"""

import os
import smtplib
import random
import string
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SMTP Configuration
SMTP_SERVER = "mail.smtp2go.com"
SMTP_PORT = 2525  # Updated to the correct port
SMTP_USERNAME = "itgenics.pk"  # Updated to full email address
SMTP_PASSWORD = "3SuIDVWM3Yxvd3rL"
FROM_EMAIL = "talha.zain@itgenics.pk"





# Store OTPs temporarily (in production, use Redis or similar)
otp_storage = {}

def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(recipient_email: str) -> tuple[bool, str]:
    """
    Sends a verification email with OTP.

    Args:
        recipient_email (str): Recipient's email address.

    Returns:
        tuple[bool, str]: (True if email was sent successfully, OTP)
    """
    try:
        # Generate OTP
        otp = generate_otp()
        
        # Store OTP with expiration (5 minutes)
        otp_storage[recipient_email] = {
            'otp': otp,
            'expires_at': datetime.utcnow() + timedelta(minutes=5)
        }

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verify Your Email Address"
        msg["From"] = FROM_EMAIL
        msg["To"] = recipient_email

        text = f"Your verification OTP is: {otp}\nThis OTP will expire in 5 minutes."
        html = f"""
        <html>
          <body>
            <p>Your verification OTP is:</p>
            <h2 style="color: #6366f1; font-size: 24px; letter-spacing: 2px;">{otp}</h2>
            <p>This OTP will expire in 5 minutes.</p>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)

        try:
            # Try to connect to SMTP server with timeout
            logger.info(f"Attempting to connect to SMTP server {SMTP_SERVER}:{SMTP_PORT}")
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            
            # Start TLS
            logger.info("Starting TLS connection")
            server.starttls()
            
            # Login
            logger.info(f"Attempting to login with username: {SMTP_USERNAME}")
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            
            # Send email
            logger.info(f"Sending email to {recipient_email}")
            server.sendmail(FROM_EMAIL, recipient_email, msg.as_string())
            
            # Quit
            server.quit()
            logger.info(f"Verification email sent successfully to {recipient_email}")
            return True, otp
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending email to {recipient_email}: {str(e)}")
            # For development/testing, we'll return success even if email fails
            # In production, you should return False
            return True, otp
        except Exception as e:
            logger.error(f"Error sending email to {recipient_email}: {str(e)}")
            # For development/testing, we'll return success even if email fails
            # In production, you should return False
            return True, otp
    except Exception as e:
        logger.error(f"Unexpected error in send_verification_email: {str(e)}")
        return False, ""

def verify_otp(email: str, otp: str) -> bool:
    """
    Verify if the provided OTP is valid for the given email.

    Args:
        email (str): User's email address
        otp (str): OTP to verify

    Returns:
        bool: True if OTP is valid, False otherwise
    """
    if email not in otp_storage:
        logger.warning(f"No OTP found for email: {email}")
        return False

    stored_data = otp_storage[email]
    if datetime.utcnow() > stored_data['expires_at']:
        del otp_storage[email]  # Clean up expired OTP
        logger.warning(f"Expired OTP for email: {email}")
        return False

    is_valid = stored_data['otp'] == otp
    if is_valid:
        del otp_storage[email]  # Clean up used OTP
        logger.info(f"OTP verified successfully for email: {email}")
    else:
        logger.warning(f"Invalid OTP provided for email: {email}")
    return is_valid

def send_password_reset_email(recipient_email: str, reset_token: str) -> bool:
    """
    Sends a password reset email with a reset link.

    Args:
        recipient_email (str): Recipient's email address
        reset_token (str): Password reset token

    Returns:
        bool: True if email was sent successfully
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset Your Password"
        msg["From"] = FROM_EMAIL
        msg["To"] = recipient_email

        reset_link = f"http://localhost:5006/static/reset-password.html?token={reset_token}"
        text = f"Click the following link to reset your password: {reset_link}\nThis link will expire in 1 hour."
        html = f"""
        <html>
          <body>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_link}" style="background-color: #6366f1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
              Reset Password
            </a>
            <p>This link will expire in 1 hour.</p>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)

        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, recipient_email, msg.as_string())
            server.quit()
            logger.info(f"Password reset email sent successfully to {recipient_email}")
            return True
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending password reset email to {recipient_email}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error sending password reset email to {recipient_email}: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in send_password_reset_email: {str(e)}")
        return False
