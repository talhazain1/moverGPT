#!/usr/bin/env python
"""
Script to create API keys table and add a sample API key for company ID 23
"""

import os
import sys
import secrets
from datetime import datetime
from sqlalchemy import create_engine, text, inspect

# Get database URL from environment or use default
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 'postgresql://myuser@localhost:5432/chatbotdb'
)

def create_api_keys_table(engine):
    """Create the api_keys table if it doesn't exist"""
    inspector = inspect(engine)
    if 'api_keys' not in inspector.get_table_names():
        print("Creating api_keys table...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    key VARCHAR(255) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'active'
                )
            """))
            conn.commit()
            print("Table created successfully.")
    else:
        print("api_keys table already exists.")

def add_api_key_for_company(engine, company_id):
    """Add a sample API key for the specified company"""
    # Generate a new API key
    api_key = f"sk_{secrets.token_hex(24)}"
    
    # Check if company already has an API key
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, key FROM api_keys 
            WHERE company_id = :company_id AND status = 'active'
        """), {"company_id": company_id})
        
        existing_key = result.fetchone()
        
        if existing_key:
            print(f"Company {company_id} already has API key: {existing_key.key}")
            return existing_key.key
        
        # Insert new API key
        print(f"Adding new API key for company {company_id}...")
        conn.execute(text("""
            INSERT INTO api_keys (company_id, key, created_at, status)
            VALUES (:company_id, :api_key, :created_at, 'active')
        """), {
            "company_id": company_id,
            "api_key": api_key,
            "created_at": datetime.utcnow()
        })
        conn.commit()
        print(f"API key added successfully: {api_key}")
        return api_key

def main():
    """Main function to run the script"""
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    
    try:
        # Create the api_keys table
        create_api_keys_table(engine)
        
        # Add API key for company ID 23
        company_id = 23
        api_key = add_api_key_for_company(engine, company_id)
        
        print("\nSetup completed successfully!")
        print(f"API key for company {company_id}: {api_key}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 