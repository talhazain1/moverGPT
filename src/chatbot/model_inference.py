# model_inference.py

import os
import openai
import pickle
import json
import numpy as np

def run_inference_openai(chatbot_config, query, history=None, top_n=3):
    """
    Uses the trained model (if available) to retrieve the most relevant FAQ entries,
    build a system prompt including the chatbot’s purpose, goal, and role, and call
    OpenAI's ChatCompletion to generate a response.
    
    If no trained_model is present, returns a fallback message.
    """
    
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        raise Exception("OPENAI_API_KEY environment variable not set.")

    # Check if the chatbot has been trained (trained_model is non-None and non-empty).
    if not chatbot_config.trained_model or len(chatbot_config.trained_model) == 0:
        print("DEBUG: No trained_model found on chatbot_config. It is:", chatbot_config.trained_model)
        return "I’m not trained yet. Please train me on a knowledge base."

    # For debugging, print out the size of the trained_model in bytes.
    model_bytes = len(chatbot_config.trained_model)
    print(f"DEBUG: Found trained model of size {model_bytes} bytes.")

    try:
        model_data = pickle.loads(chatbot_config.trained_model)
    except Exception as e:
        return f"Error loading trained model: {e}"

    embeddings = model_data.get("embeddings")
    questions = model_data.get("questions", [])
    answers = model_data.get("answers", [])
    purpose = model_data.get("purpose", "general support")
    goal = model_data.get("goal", "assist users")
    role = model_data.get("role", "assistant")

    if embeddings is None or len(questions) == 0:
        print("DEBUG: Either embeddings is None or no FAQ questions found.")
        return "No FAQ data available in the trained model."

    # 1) Compute the embedding for the query.
    query_embedding_resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=query
    )
    query_vector = np.array(query_embedding_resp["data"][0]["embedding"], dtype=np.float32)

    # 2) Compute cosine similarities.
    norms = np.linalg.norm(embeddings, axis=1)
    query_norm = np.linalg.norm(query_vector)
    dot_products = np.dot(embeddings, query_vector)
    cos_sims = dot_products / (norms * query_norm + 1e-8)

    # 3) Retrieve top_n FAQ entries.
    top_indices = np.argsort(cos_sims)[::-1][:top_n]
    relevant_faqs = []
    for idx in top_indices:
        q_text = questions[idx]
        a_text = answers[idx]
        relevant_faqs.append(f"Q: {q_text}\nA: {a_text}")

    # 4) Build the system prompt.
    few_shot_context = ""
    if relevant_faqs:
        few_shot_context = "Relevant FAQs:\n" + "\n\n".join(relevant_faqs) + "\n\n"

    system_prompt = (
        f"You are {chatbot_config.bot_name or 'ChatBot'}, a chatbot designed for {purpose}. "
        f"Your goal is to {goal}, and you act as a {role}. "
        "Use the following relevant FAQ context to answer user questions accurately:\n\n"
        f"{few_shot_context}"
        "Keep your answer short, direct, and informative. Use emoticons to be engaging.\n\n"
    )

    # 5) Build the message list for ChatCompletion.
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        conversation_context = "\n".join(
            f"{msg['sender'].capitalize()}: {msg['message']}" for msg in history
        )
        messages.append({"role": "user", "content": conversation_context})
    messages.append({"role": "user", "content": f"User question: {query}"})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.6,
        )
        answer = response.choices[0].message["content"].strip()
        print("DEBUG: Inference generated answer:", answer)
        return answer
    except Exception as e:
        return f"OpenAI API error: {e}"
