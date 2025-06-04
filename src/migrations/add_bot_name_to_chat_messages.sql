-- Add bot_name column to chat_messages table
ALTER TABLE chat_messages 
ADD COLUMN bot_name VARCHAR(255); 