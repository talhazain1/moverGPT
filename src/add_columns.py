import os
import sys
from sqlalchemy import create_engine, Column, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text

# Use the PostgreSQL database URL as defined in the app config
db_uri = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost:5432/chatbotdb')

# Create engine and connect
print(f"Connecting to database: {db_uri}")
engine = create_engine(db_uri)

try:
    conn = engine.connect()
    print("Connected to the database successfully!")

    # Add the new columns safely (check if they exist first)
    print("Adding new columns to chatbot_configs table...")
    
    # Check if the columns exist before adding them
    column_check_query = text("SELECT column_name FROM information_schema.columns WHERE table_name = 'chatbot_configs'")
    result = conn.execute(column_check_query)
    existing_columns = [row[0] for row in result]
    
    # Define the columns to add
    columns_to_add = [
        {"name": "total_messages", "type": "INTEGER", "default": "0"},
        {"name": "positive_feedback_count", "type": "INTEGER", "default": "0"},
        {"name": "total_feedback_count", "type": "INTEGER", "default": "0"},
        {"name": "satisfaction_rate", "type": "FLOAT", "default": "0.0"}
    ]
    
    # Add each column if it doesn't exist
    for column in columns_to_add:
        col_name = column["name"]
        if col_name not in existing_columns:
            alter_query = text(f"ALTER TABLE chatbot_configs ADD COLUMN {col_name} {column['type']} DEFAULT {column['default']}")
            conn.execute(alter_query)
            print(f"Added column: {col_name}")
        else:
            print(f"Column {col_name} already exists, skipping")
    
    print("Column updates completed successfully")
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    if 'conn' in locals():
        conn.close()
    sys.exit(1)
    
print("Done") 