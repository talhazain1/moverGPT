-- Add the missing chatbot_id column to chatbot_configs table
ALTER TABLE chatbot_configs ADD COLUMN IF NOT EXISTS chatbot_id INTEGER;

-- Update the complete table schema to match what's expected
ALTER TABLE chatbot_configs 
    ADD COLUMN IF NOT EXISTS bot_delay INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bot_initial_message TEXT,
    ADD COLUMN IF NOT EXISTS bot_placeholder TEXT DEFAULT 'Type your message here...',
    ADD COLUMN IF NOT EXISTS custom_css TEXT,
    ADD COLUMN IF NOT EXISTS custom_js TEXT,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- Create any missing indexes
CREATE INDEX IF NOT EXISTS idx_chatbot_configs_company_id ON chatbot_configs(company_id);
CREATE INDEX IF NOT EXISTS idx_chatbot_configs_chatbot_id ON chatbot_configs(chatbot_id); 