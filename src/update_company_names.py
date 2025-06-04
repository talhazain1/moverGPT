from flask import Flask
from core.database import db, init_db
from companies.models import Company
from users.models import User
import os

app = Flask(__name__)

# Database configuration
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(app)

def update_company_names():
    """Update generic company names with more descriptive ones based on user data"""
    try:
        with app.app_context():
            # Find companies with generic names like "Company 6"
            generic_companies = Company.query.filter(Company.name.like('Company %')).all()
            
            print(f"Found {len(generic_companies)} companies with generic names")
            
            for company in generic_companies:
                # Find a user associated with this company
                user = User.query.filter_by(company_id=company.id).first()
                
                if user:
                    # Update company name to something more descriptive
                    new_name = f"{user.company_name or user.user_name}'s Company"
                    print(f"Updating company {company.id} from '{company.name}' to '{new_name}'")
                    company.name = new_name
                    db.session.add(company)
                else:
                    print(f"No user found for company {company.id}")
            
            db.session.commit()
            print("Company names updated successfully!")
            
    except Exception as e:
        print(f"Error updating company names: {str(e)}")

if __name__ == "__main__":
    update_company_names()
