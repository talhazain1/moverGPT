"""
Quick test script to ensure circular imports are resolved and models work correctly
"""

import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test importing the modules to ensure there are no circular import errors"""
    logger.info("Testing imports...")
    
    try:
        # First import the database
        from core.database import db
        logger.info("✓ Imported core.database")
        
        # Import the models
        from chatbot.moving_models import MovingConversationState, MovingBooking
        logger.info("✓ Imported chatbot.moving_models")
        
        # Import the state enums
        from chatbot.moving_chat_handler import ConversationState
        logger.info("✓ Imported ConversationState from moving_chat_handler")
        
        # Import the chat handler
        from chatbot.moving_chat_handler import MovingChatHandler
        logger.info("✓ Imported MovingChatHandler")
        
        # Import the model inference
        from chatbot.model_inference import handle_moving_query, is_moving_company
        logger.info("✓ Imported model_inference functions")
        
        # Import company models
        from companies.models import Company, MovingParameters
        logger.info("✓ Imported companies.models")
        
        logger.info("All imports successful!")
        return True
    except Exception as e:
        logger.error(f"Import error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n✅ All imports successful. No circular import errors detected.")
    else:
        print("\n❌ Import test failed. See logs for details.") 