-- Alter the trained_model column to use BYTEA type
ALTER TABLE chatbot_configs 
ALTER COLUMN trained_model TYPE BYTEA 
USING trained_model::bytea; 