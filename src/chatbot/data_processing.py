"""
Provides functions to load and preprocess knowledge base data.
"""

import json
import re
from typing import Dict

def load_knowledge_base(file_path: str) -> Dict:
    """
    Loads a JSON-based knowledge base from the given file path.
    
    Args:
        file_path (str): Path to the JSON file containing the knowledge base.
    
    Returns:
        dict: Loaded knowledge base data.
    
    Raises:
        Exception: If there is an error reading or parsing the file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise Exception(f"Error loading knowledge base from {file_path}: {e}")

def preprocess_text(text: str) -> str:
    """
    Preprocesses text by converting to lowercase, removing non-alphanumeric characters,
    and extra whitespace.
    
    Args:
        text (str): The text to preprocess.
    
    Returns:
        str: Preprocessed text.
    """
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def preprocess_knowledge_base(data: dict) -> dict:
    """
    Applies text preprocessing to all textual fields in the knowledge base.
    
    Args:
        data (dict): The raw knowledge base data.
    
    Returns:
        dict: The preprocessed knowledge base.
    """
    processed_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            processed_data[key] = preprocess_text(value)
        elif isinstance(value, list):
            processed_data[key] = [
                preprocess_text(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            processed_data[key] = value
    return processed_data
