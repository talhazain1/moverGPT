-- Drop the existing foreign key constraint
ALTER TABLE chat_sessions 
DROP CONSTRAINT chat_sessions_chatbot_id_fkey;

-- Add the new foreign key constraint referencing chatbot_configs
ALTER TABLE chat_sessions 
ADD CONSTRAINT chat_sessions_chatbot_id_fkey 
FOREIGN KEY (chatbot_id) 
REFERENCES chatbot_configs(id) 
ON DELETE CASCADE; 