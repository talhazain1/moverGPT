-- Drop and recreate the chatbot_configs table with all needed columns
DROP TABLE IF EXISTS chatbot_configs CASCADE;

CREATE TABLE chatbot_configs (
    id SERIAL PRIMARY KEY,
    company_id INTEGER,
    chatbot_id INTEGER,
    bot_name VARCHAR(255),
    bot_type VARCHAR(50),
    role VARCHAR(100),
    subscription_plan VARCHAR(50),
    version VARCHAR(50),
    configuration JSONB,
    purpose VARCHAR(100),
    goal VARCHAR(100),
    knowledge_base TEXT,
    trained_model VARCHAR(255),
    last_trained_at TIMESTAMP,
    total_messages INTEGER DEFAULT 0,
    positive_feedback_count INTEGER DEFAULT 0,
    total_feedback_count INTEGER DEFAULT 0,
    satisfaction_rate FLOAT DEFAULT 0.0,
    prompt_template TEXT,
    display_name VARCHAR(255),
    avatar_url VARCHAR(255),
    primary_color VARCHAR(50) DEFAULT '#3498db',
    chat_position VARCHAR(20) DEFAULT 'right',
    bot_delay INTEGER DEFAULT 0,
    bot_initial_message TEXT,
    bot_placeholder TEXT DEFAULT 'Type your message here...',
    custom_css TEXT,
    custom_js TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_chatbot_configs_company_id ON chatbot_configs(company_id);
CREATE INDEX idx_chatbot_configs_chatbot_id ON chatbot_configs(chatbot_id); 