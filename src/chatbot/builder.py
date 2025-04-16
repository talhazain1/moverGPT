"""
Integrates data processing, dynamic model training, and database storage to build a chatbot instance.
"""

from chatbot import data_processing, model_training
from chatbot.models import ChatbotConfig
from core.database import db

def build_chatbot(client_id: int, knowledge_base_file_path: str, configuration: dict) -> ChatbotConfig:
    """
    Builds a chatbot instance for a client with dynamic configuration.
    
    Process:
      1. Load the knowledge base from the provided file.
      2. Preprocess the data.
      3. Train the model using the knowledge base and configuration that includes dynamic
         inputs (purpose, goal, role).
      4. Create and save a ChatbotConfig record in the database.
    
    Args:
        client_id (int): The identifier of the client.
        knowledge_base_file_path (str): File path to the knowledge base JSON.
        configuration (dict): Configuration for the chatbot, including keys like 'purpose',
                              'goal', and 'role', along with any other settings.
    
    Returns:
        ChatbotConfig: The database record for the chatbot configuration.
    
    Raises:
        Exception: If any step fails.
    """
    # Load and preprocess the knowledge base
    knowledge_base = data_processing.load_knowledge_base(knowledge_base_file_path)
    processed_knowledge_base = data_processing.preprocess_knowledge_base(knowledge_base)
    
    # Train the chatbot model using the preprocessed data and dynamic configuration
    trained_model = model_training.train_model(processed_knowledge_base, configuration)
    
    # Create a new ChatbotConfig instance with dynamic fields
    chatbot_config = ChatbotConfig(
        client_id=client_id,
        configuration=configuration,
        purpose=configuration.get("purpose"),
        goal=configuration.get("goal"),
        role=configuration.get("role"),
        knowledge_base=processed_knowledge_base,
        trained_model=trained_model
    )
    
    try:
        db.session.add(chatbot_config)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Database error while saving chatbot configuration: {e}")
    
    return chatbot_config
