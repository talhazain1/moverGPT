-- Create moving_conversation_states table
CREATE TABLE IF NOT EXISTS moving_conversation_states (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    current_state VARCHAR(50) NOT NULL,
    collected_info JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, session_id)
);

-- Create trigger to update updated_at
CREATE OR REPLACE FUNCTION update_moving_conversation_states_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_moving_conversation_states_updated_at
    BEFORE UPDATE ON moving_conversation_states
    FOR EACH ROW
    EXECUTE FUNCTION update_moving_conversation_states_updated_at(); 