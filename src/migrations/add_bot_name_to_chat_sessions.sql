-- Add bot_name column to chat_sessions
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS bot_name VARCHAR(255);

-- Populate bot_name from chatbot_configs
UPDATE chat_sessions cs
SET bot_name = cc.bot_name
FROM chatbot_configs cc
WHERE cs.chatbot_id = cc.id;

-- Set default value for any remaining NULL bot_names
UPDATE chat_sessions
SET bot_name = 'Untitled Chatbot'
WHERE bot_name IS NULL; 