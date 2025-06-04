#!/usr/bin/env python
"""
This script fixes missing fields in chatbot_configs records.
It ensures all required fields are properly set, including timestamps and version.
"""

import os
import sys

# Add the project directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from core.database import db
from chatbot.models import ChatbotConfig
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm.attributes import flag_modified

def fix_chatbot_configs():
    try:
        print("Starting chatbot_configs fix...")
        
        # Get all chatbots
        chatbots = ChatbotConfig.query.all()
        
        print(f"Found {len(chatbots)} chatbot records to check")
        
        updates_needed = 0
        
        for chatbot in chatbots:
            updated = False
            
            # Fix created_at
            if not hasattr(chatbot, 'created_at') or chatbot.created_at is None:
                try:
                    # Check if column exists
                    db.session.execute(text("SELECT created_at FROM chatbot_configs LIMIT 1"))
                    # If we get here, the column exists
                    chatbot.created_at = datetime.utcnow()
                    updated = True
                    print(f"Added created_at for chatbot {chatbot.id}")
                except (OperationalError, ProgrammingError) as e:
                    print(f"Warning: created_at column doesn't exist: {e}")
            
            # Fix updated_at
            if not hasattr(chatbot, 'updated_at') or chatbot.updated_at is None:
                try:
                    # Check if column exists
                    db.session.execute(text("SELECT updated_at FROM chatbot_configs LIMIT 1"))
                    # If we get here, the column exists
                    chatbot.updated_at = datetime.utcnow()
                    updated = True
                    print(f"Added updated_at for chatbot {chatbot.id}")
                except (OperationalError, ProgrammingError) as e:
                    print(f"Warning: updated_at column doesn't exist: {e}")
            
            # Fix version
            if chatbot.version is None:
                chatbot.version = 1
                updated = True
                print(f"Fixed version for chatbot {chatbot.id}")
            elif not isinstance(chatbot.version, int):
                try:
                    chatbot.version = int(chatbot.version)
                    updated = True
                    print(f"Converted version to int for chatbot {chatbot.id}")
                except (ValueError, TypeError):
                    chatbot.version = 1
                    updated = True
                    print(f"Reset invalid version for chatbot {chatbot.id}")
            
            # Fix configuration
            if chatbot.configuration is None:
                chatbot.configuration = {}
                updated = True
                print(f"Initialized empty configuration for chatbot {chatbot.id}")
            else:
                # Make sure configuration has required fields
                required_fields = ['description', 'welcome_message']
                config_updated = False
                
                for field in required_fields:
                    if field not in chatbot.configuration:
                        chatbot.configuration[field] = ''
                        config_updated = True
                
                if config_updated:
                    flag_modified(chatbot, "configuration")
                    updated = True
                    print(f"Added missing fields to configuration for chatbot {chatbot.id}")
            
            # Fix knowledge_base
            if chatbot.knowledge_base is None:
                chatbot.knowledge_base = {}
                updated = True
                print(f"Initialized empty knowledge_base for chatbot {chatbot.id}")
            
            if updated:
                updates_needed += 1
        
        if updates_needed > 0:
            db.session.commit()
            print(f"Applied fixes to {updates_needed} chatbot records")
        else:
            print("No fixes needed for chatbot records")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error fixing chatbot configs: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = fix_chatbot_configs()
    if success:
        print("Chatbot configs fixed successfully!")
    else:
        print("Failed to fix chatbot configs.")
        sys.exit(1) 