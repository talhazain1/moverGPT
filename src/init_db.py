import os
from flask import Flask
from core.database import db, init_db
from sqlalchemy import text

# Import all models
from chatbot.models import ChatMessage, ChatSession, ChatbotConfig, ChatbotInteraction, Chat, Train
from users.models import User
from admin.models import AdminUser
from admin_panel.models import SupportTicket, SupportMessage, MessageAttachment, KnowledgeBase, Message
from companies.models import Company, MovingParameters

app = Flask(__name__)

# Database configuration
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(app)

def init_database():
    try:
        # Create all tables
        db.create_all()
        print("Database initialized successfully!")
        
        # Verify tables were created
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            print("\nCreated tables:")
            for table in tables:
                print(f"- {table}")
                
        # Seed default Company with id=6 if not exists
        if not Company.query.get(6):
            default_company = Company(
                name='Default Company',
                email='company6@example.com',
                phone='000-000-0000',
                website='https://defaultcompany.example.com',
                business_address='123 Default St, City, Country',
                niche='Default',
                subscription_plan='basic',
                status='active'
            )
            default_company.id = 6
            db.session.add(default_company)
            db.session.commit()
            print("Seeded default Company with id=6")
            
    except Exception as e:
        print(f"Error initializing database: {str(e)}")

if __name__ == "__main__":
    with app.app_context():
        init_database() 