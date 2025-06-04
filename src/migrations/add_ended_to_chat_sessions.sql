-- Add ended column to chat_sessions table
ALTER TABLE chat_sessions 
ADD COLUMN ended BOOLEAN DEFAULT FALSE; 