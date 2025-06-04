from flask import Flask
from core.database import db, init_db
from companies.models import Company
from admin_panel.models import SupportTicket
from users.models import User
import os
import json

app = Flask(__name__)

# Use the same database configuration as the main app
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(app)

def debug_companies_and_tickets():
    """Print diagnostic information about companies and tickets"""
    try:
        with app.app_context():
            print("\n=== DATABASE DIAGNOSTICS ===\n")
            
            # Check all companies
            companies = Company.query.all()
            print(f"Total companies: {len(companies)}")
            for company in companies:
                print(f"Company ID: {company.id}, Name: {company.name}, Email: {company.email}")
            
            print("\n=== GENERIC COMPANY NAMES ===\n")
            generic_companies = Company.query.filter(Company.name.like('Company %')).all()
            print(f"Companies with generic names: {len(generic_companies)}")
            for company in generic_companies:
                print(f"Company ID: {company.id}, Name: {company.name}")
                # Find users associated with this company
                users = User.query.filter_by(company_id=company.id).all()
                print(f"  Associated users: {len(users)}")
                for user in users:
                    print(f"  - User ID: {user.id}, Name: {user.user_name}, Email: {user.user_email}")
            
            print("\n=== SUPPORT TICKETS ===\n")
            tickets = SupportTicket.query.all()
            print(f"Total tickets: {len(tickets)}")
            for ticket in tickets:
                company = Company.query.get(ticket.company_id)
                user = User.query.get(ticket.user_id)
                print(f"Ticket: {ticket.ticket_number}")
                print(f"  Subject: {ticket.subject}")
                print(f"  Company ID: {ticket.company_id}")
                print(f"  Company Name: {company.name if company else 'None'}")
                print(f"  User ID: {ticket.user_id}")
                print(f"  User Name: {user.user_name if user else 'None'}")
                print(f"  User Email: {user.user_email if user else 'None'}")
                print("  ---")
            
    except Exception as e:
        print(f"Error in diagnostics: {str(e)}")

if __name__ == "__main__":
    debug_companies_and_tickets()
