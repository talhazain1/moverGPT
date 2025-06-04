#!/usr/bin/env python
"""
This script updates existing chat_sessions with bot_name values from their related chatbot_configs.
It can be run after the migration that adds the bot_name column to chat_sessions.
"""

import os
import sys

# Add the project directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database import db
from src.chatbot.models import ChatSession, ChatbotConfig
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

def fix_chat_sessions():
    try:
        print("Starting chat_sessions fix...")
        
        # First check if the bot_name column exists
        try:
            # Try to select from the column to see if it exists
            db.session.execute(text("SELECT bot_name FROM chat_sessions LIMIT 1"))
            print("The bot_name column exists in chat_sessions table.")
        except (OperationalError, ProgrammingError) as e:
            print("Error: The bot_name column does not exist in chat_sessions table.")
            print("Please run the migration to add this column first.")
            print(f"Error details: {str(e)}")
            return False
        
        # Get all chat sessions that have a chatbot_id but no bot_name
        sessions = ChatSession.query.filter(
            ChatSession.chatbot_id.isnot(None),
            (ChatSession.bot_name.is_(None) | (ChatSession.bot_name == ''))
        ).all()
        
        print(f"Found {len(sessions)} chat sessions with missing bot_name.")
        
        # Batch process updates to avoid long transactions
        batch_size = 1000
        total_updated = 0
        
        # Get all chatbots with their IDs for faster lookup
        chatbots = {c.id: c for c in ChatbotConfig.query.all()}
        print(f"Loaded {len(chatbots)} chatbots for reference.")
        
        for i in range(0, len(sessions), batch_size):
            batch = sessions[i:i+batch_size]
            updated_in_batch = 0
            
            for session in batch:
                chatbot = chatbots.get(session.chatbot_id)
                if chatbot:
                    session.bot_name = chatbot.bot_name or f"Chatbot {chatbot.id}"
                    updated_in_batch += 1
            
            db.session.commit()
            total_updated += updated_in_batch
            print(f"Updated {updated_in_batch} sessions in batch {i//batch_size + 1}")
        
        print(f"Successfully updated {total_updated} chat sessions with bot_name values.")
        
        # Verify the results
        missing_count = ChatSession.query.filter(
            ChatSession.chatbot_id.isnot(None),
            (ChatSession.bot_name.is_(None) | (ChatSession.bot_name == ''))
        ).count()
        
        print(f"Remaining sessions with missing bot_name: {missing_count}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error fixing chat sessions: {str(e)}")
        return False

if __name__ == "__main__":
    success = fix_chat_sessions()
    if success:
        print("Chat sessions fixed successfully!")
    else:
        print("Failed to fix chat sessions.")
        sys.exit(1) 