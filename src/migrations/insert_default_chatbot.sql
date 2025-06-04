-- Update existing chatbot for company 1
UPDATE chatbot_configs 
SET 
    bot_name = 'Michael',
    chatbot_id = '1',
    role = 'Moving Consultant',
    purpose = 'Customer Service and Lead Generation',
    goal = 'Help customers with their moving needs and generate leads',
    configuration = '{"display_name": "Michael", "avatar_url": "/static/avatars/michael.png", "primary_color": "#3498db", "chat_position": "right", "bot_delay": 0, "bot_initial_message": "Hello! I''m Michael. How can I help you today?", "bot_placeholder": "Type your message here..."}',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1; 