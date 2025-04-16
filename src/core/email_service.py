"""
Email Service Module

This module provides functions for sending email verification messages.
It uses SMTP to send verification emails with a link or OTP.
Ensure to set these environment variables:
  - SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, FROM_EMAIL
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "mail.smtp2go.com"
SMTP_PORT = 567
SMTP_USERNAME = "itgenics.pk"
SMTP_PASSWORD = "wsx535Tl5DJuE5Dh"
FROM_EMAIL = "talha.zain@itgenics.pk"

def send_verification_email(recipient_email: str, verification_link: str) -> bool:
    """
    Sends a verification email with the provided verification link.

    Args:
        recipient_email (str): Recipient's email address.
        verification_link (str): Link (or OTP) for email verification.

    Returns:
        bool: True if the email was sent successfully, else False.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verify Your Email Address"
        msg["From"] = FROM_EMAIL
        msg["To"] = recipient_email

        text = f"Please verify your email by clicking the link:\n{verification_link}"
        html = f"""
        <html>
          <body>
            <p>Please verify your email address by clicking the link below:</p>
            <a href="{verification_link}">Verify Email</a>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        # In production, log the error appropriately.
        print(f"Error sending email: {e}")
        return False
