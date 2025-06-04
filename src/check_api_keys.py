"""
Check API Keys Table
Attempt to query the api_keys table
"""
from main import app
from core.database import db
from sqlalchemy import text

def check_api_keys():
    """Try different queries against the api_keys table"""
    with app.app_context():
        try:
            # Try a basic query without requiring active column
            result = db.session.execute(text("SELECT id, company_id, key, created_at FROM api_keys LIMIT 5"))
            rows = result.fetchall()
            
            print("Basic query results:")
            for row in rows:
                print(f"ID: {row[0]}, Company ID: {row[1]}, Key: {row[2][:10]}..., Created: {row[3]}")
            
            # Now try to import and use the models
            from admin.models import ApiKey
            api_keys = ApiKey.query.limit(5).all()
            
            print("\nUsing ApiKey model:")
            for key in api_keys:
                print(f"ID: {key.id}, Company ID: {key.company_id}, Key: {key.key[:10]}..., Active: {getattr(key, 'active', 'N/A')}")
                
        except Exception as e:
            print(f"Error checking api_keys: {e}")

if __name__ == "__main__":
    check_api_keys() 