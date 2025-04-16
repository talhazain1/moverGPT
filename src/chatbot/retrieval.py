import os
import openai
import numpy as np

def get_embedding(text, model="text-embedding-ada-002"):
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    response = openai.Embedding.create(input=[text], model=model)
    # Return embedding as a numpy array.
    embedding = response['data'][0]['embedding']
    return np.array(embedding)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)

def get_relevant_faqs(query, knowledge_base, top_n=3):
    """
    Given a query string and a knowledge_base dictionary containing a "faqs" key (a list of FAQs),
    compute embeddings for the query and for each FAQ (using the concatenated question+answer).
    Returns a formatted string with the top_n most similar FAQs.
    """
    if "faqs" not in knowledge_base or not isinstance(knowledge_base["faqs"], list):
        return ""
    
    faqs = knowledge_base["faqs"]
    query_embedding = get_embedding(query)
    similarities = []
    for faq in faqs:
        text = faq.get("question", "") + " " + faq.get("answer", "")
        faq_embedding = get_embedding(text)
        sim = cosine_similarity(query_embedding, faq_embedding)
        similarities.append(sim)
    
    # Get indices of top_n FAQs
    top_indices = np.argsort(similarities)[-top_n:][::-1]
    formatted = "\n".join([f"Q: {faqs[i]['question']}\nA: {faqs[i]['answer']}" for i in top_indices])
    return formatted
