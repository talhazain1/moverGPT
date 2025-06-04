"""
Check API Keys Table Schema
Prints the current schema of the api_keys table
"""
from main import app
from core.database import db
from sqlalchemy import text
import json

def check_table_schema():
    """Check the schema of the api_keys table"""
    with app.app_context():
        try:
            # Get the column information for the api_keys table
            result = db.session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'api_keys'"))
            columns = result.fetchall()
            
            print("API Keys Table Schema:")
            for column in columns:
                print(f"Column: {column[0]}, Type: {column[1]}")
            
            # Now let's check what ApiKey models we're using
            from admin.models import ApiKey as AdminApiKey
            from chatbot.models import ApiKey as ChatbotApiKey
            
            # Print the model attributes
            print("\nAdmin ApiKey Model columns:")
            for column in AdminApiKey.__table__.columns:
                print(f"Column: {column.name}, Type: {column.type}")
            
            print("\nChatbot ApiKey Model columns:")
            for column in ChatbotApiKey.__table__.columns:
                print(f"Column: {column.name}, Type: {column.type}")
            
        except Exception as e:
            print(f"Error checking table schema: {e}")

if __name__ == "__main__":
    check_table_schema() 