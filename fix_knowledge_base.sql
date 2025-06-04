-- Fix the knowledge_base column data type
ALTER TABLE chatbot_configs DROP COLUMN IF EXISTS knowledge_base;
ALTER TABLE chatbot_configs ADD COLUMN knowledge_base JSONB; 