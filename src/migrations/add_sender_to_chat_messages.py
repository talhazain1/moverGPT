import logging
from sqlalchemy import text, inspect
from core.database import db

logger = logging.getLogger(__name__)

def run_migration():
    """
    Migration script to add the 'sender' column to chat_messages table.
    """
    logger.info("Starting chat_messages sender column migration")
    try:
        inspector = inspect(db.engine)
        table_exists = 'chat_messages' in inspector.get_table_names()
        if not table_exists:
            logger.warning("chat_messages table does not exist; skipping sender column migration")
            return True
        # Check if 'sender' column exists
        columns = [col['name'] for col in inspector.get_columns('chat_messages')]
        if 'sender' in columns:
            logger.info("'sender' column already exists in chat_messages table")
            return True
        # Add 'sender' column
        db.session.execute(text(
            """
            ALTER TABLE chat_messages
            ADD COLUMN sender VARCHAR(50) NOT NULL DEFAULT 'user'
            """
        ))
        db.session.commit()
        logger.info("Added 'sender' column to chat_messages table")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding sender column to chat_messages: {str(e)}")
        return False 