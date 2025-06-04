-- SQL script to create the missing chatbot_configs table

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    website VARCHAR(255),
    logo VARCHAR(255),
    niche VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

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
); 