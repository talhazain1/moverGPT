#!/usr/bin/env python3
"""
Script to check and fix database schema issues for metrics.
This checks chat_sessions and related tables to make sure they exist
and have the correct columns.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection string from environment or use default
DB_URL = os.environ.get(
    'DATABASE_URL', 'postgresql://movergptuser:M0v3rGPT_2025!@127.0.0.1:5432/movergptdb'
)

def get_engine():
    """Get SQLAlchemy engine with connection to database"""
    try:
        engine = create_engine(DB_URL)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return engine
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        sys.exit(1)

def check_table_schema(engine, table_name):
    """Check if table exists and print its schema"""
    try:
        with engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text(f"SELECT to_regclass('public.{table_name}')"))
            table_exists = result.scalar() is not None
            
            if not table_exists:
                logger.warning(f"Table '{table_name}' does not exist")
                return False
            
            # Get table columns
            result = conn.execute(text(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            logger.info(f"Table '{table_name}' exists with {len(columns)} columns:")
            for col in columns:
                logger.info(f"  - {col[0]} ({col[1]})")
            
            return True
    except Exception as e:
        logger.error(f"Error checking table '{table_name}': {e}")
        return False

def main():
    """Main function to check database tables"""
    logger.info("Starting database table check")
    
    engine = get_engine()
    
    # Check important tables for metrics
    tables_to_check = [
        'chat_sessions',
        'chat_messages',
        'chatbot_configs',
        'support_tickets',
        'moving_quote_requests'
    ]
    
    for table in tables_to_check:
        check_table_schema(engine, table)
    
    # Try running the most problematic query from metrics
    try:
        with engine.connect() as conn:
            # First check if any chatbots exist
            result = conn.execute(text(f"SELECT id FROM chatbot_configs LIMIT 5"))
            chatbots = result.fetchall()
            
            if not chatbots:
                logger.warning("No chatbots found in database")
                return
            
            # Get one chatbot ID for testing
            chatbot_id = chatbots[0][0]
            logger.info(f"Testing with chatbot_id: {chatbot_id}")
            
            # Try the query that's failing
            result = conn.execute(text(f"""
                SELECT COUNT(*) 
                FROM chat_sessions 
                WHERE chatbot_id = {chatbot_id}
            """))
            count = result.scalar() or 0
            logger.info(f"Chat sessions count for chatbot {chatbot_id}: {count}")
            
            # Try getting message count
            result = conn.execute(text(f"""
                SELECT COUNT(*) 
                FROM chat_messages 
                WHERE session_id IN (
                    SELECT id FROM chat_sessions 
                    WHERE chatbot_id = {chatbot_id}
                )
            """))
            count = result.scalar() or 0
            logger.info(f"Chat messages count for chatbot {chatbot_id}: {count}")
            
    except Exception as e:
        logger.error(f"Error testing metrics queries: {e}")

if __name__ == "__main__":
    main() 