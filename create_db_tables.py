import psycopg2
from psycopg2 import sql
import os
import sys

# Database connection parameters
db_params = {
    'dbname': 'movergptdb',
    'user': 'movergptuser',
    'password': 'M0v3rGPT_2025!',
    'host': '127.0.0.1',
    'port': '5432'
}

print(f"Connecting to database: {db_params['dbname']} as {db_params['user']}...")

try:
    # Connect to PostgreSQL
    conn = psycopg2.connect(**db_params)
    conn.autocommit = True
    cursor = conn.cursor()
    print("✓ Connected to database successfully")

    # Create users table
    print("Creating users table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        user_name VARCHAR(255),
        user_phone VARCHAR(50),
        user_email VARCHAR(255) UNIQUE,
        company_id INTEGER,
        company_name VARCHAR(255),
        company_phone VARCHAR(50),
        business_address TEXT,
        company_website VARCHAR(255),
        company_logo VARCHAR(255),
        niche VARCHAR(255),
        is_verified BOOLEAN DEFAULT FALSE,
        subscription_plan VARCHAR(50),
        subscription_expires_at TIMESTAMP,
        subscription_status VARCHAR(50),
        password_hash VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("✓ Users table created or already exists")
    
    # Create admin_users table
    print("Creating admin_users table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE,
        email VARCHAR(255) UNIQUE,
        password_hash VARCHAR(255),
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("✓ Admin users table created or already exists")
    
    # Create companies table
    print("Creating companies table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255),
        phone VARCHAR(50),
        address TEXT,
        website VARCHAR(255),
        logo VARCHAR(255),
        niche VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("✓ Companies table created or already exists")
    
    # Create chatbots table
    print("Creating chatbots table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chatbots (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255),
        company_id INTEGER,
        prompt_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )
    """)
    print("✓ Chatbots table created or already exists")
    
    # Create chatbot_configs table
    print("Creating chatbot_configs table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chatbot_configs (
        id SERIAL PRIMARY KEY,
        company_id INTEGER,
        bot_name VARCHAR(255),
        bot_type VARCHAR(50),
        prompt_template TEXT,
        display_name VARCHAR(255),
        avatar_url VARCHAR(255),
        primary_color VARCHAR(50) DEFAULT '#3498db',
        chat_position VARCHAR(20) DEFAULT 'right',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )
    """)
    print("✓ Chatbot configs table created or already exists")
    
    # Create chat_sessions table
    print("Creating chat_sessions table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id SERIAL PRIMARY KEY,
        chatbot_id INTEGER,
        session_id VARCHAR(255),
        user_identifier VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chatbot_id) REFERENCES chatbots(id) ON DELETE CASCADE
    )
    """)
    print("✓ Chat sessions table created or already exists")
    
    # Create chat_messages table
    print("Creating chat_messages table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        session_id INTEGER,
        role VARCHAR(50),
        content TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
    )
    """)
    print("✓ Chat messages table created or already exists")
    
    # Create api_keys table
    print("Creating api_keys table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id SERIAL PRIMARY KEY,
        company_id INTEGER,
        api_key VARCHAR(255) UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )
    """)
    print("✓ API keys table created or already exists")
    
    cursor.close()
    conn.close()
    print("\n✅ Database tables created successfully!")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)