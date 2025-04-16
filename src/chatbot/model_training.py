# model_training.py

import os
import openai
import pickle
import numpy as np

def train_model(knowledge_base: dict, configuration: dict) -> bytes:
    """
    Trains a chatbot model by embedding FAQ questions using OpenAI.
    
    knowledge_base should have the format:
      { "faqs": [ {"question": "...", "answer": "..."}, ... ] }
    
    configuration can include: { "purpose": "...", "goal": "...", "role": "..." }
    
    Returns:
      A pickled dictionary containing embeddings, questions, answers, and dynamic parameters.
    """
    
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        raise Exception("OPENAI_API_KEY environment variable not set.")
    
    faqs = knowledge_base.get("faqs", [])
    if not faqs:
        raise ValueError("knowledge_base must contain a 'faqs' list with at least one FAQ entry.")
    
    purpose = configuration.get("purpose", "default_purpose")
    goal = configuration.get("goal", "default_goal")
    role = configuration.get("role", "assistant")
    
    questions = []
    answers = []
    embeddings = []
    
    for item in faqs:
        q = item.get("question")
        a = item.get("answer")
        if q and a:
            questions.append(q)
            answers.append(a)
            # Generate an embedding for the question.
            response = openai.Embedding.create(
                model="text-embedding-ada-002",
                input=q
            )
            embedding_vector = response["data"][0]["embedding"]
            embeddings.append(embedding_vector)
    
    if not questions:
        raise ValueError("No valid Q/A pairs found in 'faqs'.")
    
    model_data = {
        "embeddings": np.array(embeddings, dtype=np.float32),  # Save as float32 numpy array.
        "questions": questions,
        "answers": answers,
        "purpose": purpose,
        "goal": goal,
        "role": role
    }
    pickled_model = pickle.dumps(model_data)
    return pickled_model
