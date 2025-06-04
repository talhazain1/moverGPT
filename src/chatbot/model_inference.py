# model_inference.py

import os
import openai
import pickle
import json
import logging
import numpy as np
from datetime import datetime
from core.database import db
import re
import traceback
import random

# Only import ConversationState enum which doesn't cause circular imports
from chatbot.moving_chat_handler import ConversationState

# Create a logger
logger = logging.getLogger(__name__)

# In-memory cache for conversation states when database operations fail
# Format: {(company_id, session_id): {state_dict}}
CONVERSATION_STATE_CACHE = {}

def run_inference_openai(chatbot_config, query, history=None, session_id=None, top_n=3):
    """
    Uses the trained model (if available) to retrieve the most relevant FAQ entries,
    build a system prompt including the chatbot's purpose, goal, and role, and call
    OpenAI's ChatCompletion to generate a response.
    
    For moving companies, this also handles special cases like cost estimation,
    booking flows, and complaint handling.
    
    If no trained_model is present, returns a fallback message.
    
    Args:
        chatbot_config: Configuration object containing trained model and metadata
        query (str): The user's current query
        history (list, optional): Previous messages in the conversation
        session_id (int, optional): Session ID for state tracking
        top_n (int, optional): Number of FAQ entries to consider
        
    Returns:
        str: Generated response from the chatbot
    """
    
    # Ensure we start with a clean database session to avoid transaction errors
    try:
        db.session.rollback()
        logger.debug("Successfully rolled back any pending transactions at start of inference")
    except Exception as e:
        logger.warning(f"Error rolling back session at start of inference: {e}")
    
    # Handle simple greetings with random variations
    greeting_patterns = re.compile(r'^\s*(hi|hello|hey|good\s(morning|afternoon|evening))[\!\.]*\s*$', re.IGNORECASE)
    if query and greeting_patterns.match(query):
        greetings = [
            "Hey there! What can I help you with today? 😊",
            "Hi! How can I assist you today? 🌟",
            "Hello! What do you need help with? 🤖",
            "Hi there! How may I be of service? 👍",
            "Hello! Feel free to ask me anything. 💬"
        ]
        return random.choice(greetings)
    
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        logger.error("OPENAI_API_KEY environment variable not set.")
        if query and "mov" in query.lower() and ("new york" in query.lower() or "boston" in query.lower()):
            # Special handling for moving-related queries when API key is missing
            return "I'm sorry, but I can't provide a moving estimate right now due to a configuration issue. Please try again later or contact customer support."
        else:
            # Generic error for other queries
            raise Exception("OPENAI_API_KEY environment variable not set. Please configure your API key to use this feature.")
    
    # For moving companies, always attempt to route through the specialized moving chat handler first
    company_id = chatbot_config.company_id
    if is_moving_company(company_id) and session_id:
        # Call the internal handle_moving_query function defined later in this module
        moving_response = handle_moving_query(company_id, session_id, query, history)
        
        if moving_response:
            logger.info(f"Moving handler returned a response: '{moving_response[:50]}...'" )
            return moving_response
    
    # Before accessing the trained model, ensure we have a clean session
    try:
        db.session.rollback()
    except Exception as e:
        logger.warning(f"Error rolling back session before checking trained model: {e}")
    
    # Check if the chatbot has been trained (trained_model is non-None and non-empty).
    if not chatbot_config.trained_model or len(chatbot_config.trained_model) == 0:
        logger.warning(f"No trained_model found on chatbot_config id={chatbot_config.id}")
        return "I'm not trained yet. Please train me on a knowledge base."

    # For debugging, print out the size of the trained_model in bytes.
    model_bytes = len(chatbot_config.trained_model)
    logger.debug(f"Found trained model of size {model_bytes} bytes.")

    try:
        model_data = pickle.loads(chatbot_config.trained_model)
    except Exception as e:
        logger.error(f"Error loading trained model: {e}")
        return f"Error loading trained model: {e}"

    embeddings = model_data.get("embeddings")
    questions = model_data.get("questions", [])
    answers = model_data.get("answers", [])
    purpose = model_data.get("purpose", "general support")
    goal = model_data.get("goal", "assist users")
    role = model_data.get("role", "assistant")

    if embeddings is None or len(questions) == 0:
        logger.warning("Either embeddings is None or no FAQ questions found.")
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
    top_indices = np.argsort(cos_sims)[::-1][:top_n*2]  # Get more candidates for filtering
    relevant_faqs = []
    
    # Get the best similarity score to set an adaptive threshold
    if len(top_indices) > 0:
        best_similarity = cos_sims[top_indices[0]]
        # Use adaptive threshold based on best match, but not lower than 0.6
        # This ensures we get good matches even when the best isn't very high
        similarity_threshold = max(0.6, best_similarity * 0.8)
        logger.debug(f"Best similarity: {best_similarity:.4f}, using threshold: {similarity_threshold:.4f}")
    else:
        similarity_threshold = 0.6
    
    for idx in top_indices:
        similarity = cos_sims[idx]
        if similarity >= similarity_threshold:
            q_text = questions[idx]
            a_text = answers[idx]
            logger.debug(f"Including FAQ with similarity {similarity:.4f}: {q_text[:50]}...")
            relevant_faqs.append(f"Q: {q_text}\nA: {a_text}")
    
    # If we filtered out too many, include at least one FAQ for context if available
    if len(relevant_faqs) == 0 and len(top_indices) > 0:
        best_idx = top_indices[0]
        q_text = questions[best_idx]
        a_text = answers[best_idx]
        best_similarity = cos_sims[best_idx]
        logger.debug(f"Including best available FAQ with similarity {best_similarity:.4f}: {q_text[:50]}...")
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
        "Important instructions:\n"
        "1. Match your answer to the company's policies and FAQs when applicable.\n"
        "2. Maintain continuity with previous messages in the conversation.\n"
        "3. If the FAQ doesn't directly answer the question, use your knowledge but stay consistent with company policies.\n"
        "4. Include appropriate emojis to make your responses friendly and engaging.\n"
        "5. Be polite and conversational while keeping responses informative and reasonably concise.\n"
        "6. Include all necessary details in your response to fully answer the user's question.\n\n"
        "7. Try to keep your answer short, direct, and informative.\n"
    )

    # 5) Build the message list for ChatCompletion.
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        # Convert history to the format needed for the ChatCompletion API
        for msg in history:
            if msg['sender'] == 'user':
                messages.append({"role": "user", "content": msg['message']})
            else:
                messages.append({"role": "assistant", "content": msg['message']})
        
        # Add the current query as the latest user message
        messages.append({"role": "user", "content": query})
    else:
        # If no history, just add the current query
        messages.append({"role": "user", "content": query})

    # Log message count for debugging
    logger.debug(f"Sending {len(messages)} messages to OpenAI API")
    if len(messages) > 2:
        logger.debug(f"Including {len(messages)-2} messages of conversation history")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=200,  # Increased to allow more detailed responses with emojis
            temperature=0.7,  # Slightly increased from 0.6 for more natural responses
        )
        answer = response.choices[0].message["content"].strip()
        logger.debug(f"Inference generated answer: {answer[:50]}...")
        return answer
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return f"OpenAI API error: {e}"

def is_moving_company(company_id):
    """Check if the company is a moving company based on niche or other criteria"""
    try:
        # Always ensure we have a clean database session
        try:
            db.session.rollback()
        except:
            logger.warning("Error rolling back session in is_moving_company")
            
        from companies.models import Company
        
        logger.info(f"Checking if company_id={company_id} is a moving company")
        
        try:
            company = Company.query.get(company_id)
            if not company:
                logger.warning(f"Company with id={company_id} not found")
                
                # For development/testing purposes - treat as a moving company by default
                logger.info(f"Treating company_id={company_id} as a moving company for development")
                return True
            
            # Check if MovingParameters exist for this company
            try:
                from companies.models import MovingParameters
                params = MovingParameters.query.filter_by(company_id=company_id).first()
                if params:
                    logger.info(f"Company {company_id} has moving parameters, identified as moving company")
                    return True
            except Exception as params_error:
                # If there's an error (like permission issues), log and treat as moving company
                logger.error(f"Error checking MovingParameters: {params_error}")
                return True
            
            # Check company niche if parameters don't exist
            company_niche = company.niche.lower() if company.niche else ""
            company_name = company.name.lower() if company.name else ""
            
            # Check for moving-related keywords in niche or company name
            moving_keywords = ['mov', 'reloc', 'shift', 'haul', 'transport', 'logistic']
            is_moving = any(keyword in company_niche for keyword in moving_keywords) or any(keyword in company_name for keyword in moving_keywords)
            
            if is_moving:
                logger.info(f"Company {company_id} identified as moving company based on niche/name")
                return True
            
            logger.info(f"Company {company_id} is not a moving company")
            return False
            
        except Exception as db_error:
            logger.error(f"Database error checking if company is a moving company: {db_error}")
            # Be optimistic - assume it's a moving company if there's an error checking
            return True
            
    except Exception as e:
        logger.error(f"Error checking if company is a moving company: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Be optimistic - assume it's a moving company if there's an error checking
        return True

def handle_moving_query(company_id, session_id, query, history=None):
    """
    Handle moving-specific queries using the MovingChatHandler
    
    Args:
        company_id (int): Company ID
        session_id (int): Chat session ID
        query (str): The user's query
        history (list, optional): Previous messages in the conversation
        
    Returns:
        str: Response message or None if general query
    """
    try:
        # For stateful moving conversations, skip generic classification gating
        # Always process through the MovingChatHandler to respect conversation state and date logic

        # Always ensure we have a clean database session at the start
        try:
            from core.database import db
            db.session.rollback()
            logger.debug("Successfully rolled back any pending transactions at start of handle_moving_query")
        except Exception as e:
            logger.warning(f"Error rolling back session in handle_moving_query: {e}")
            
        # Import models inside function to avoid circular imports
        from chatbot.moving_chat_handler import MovingChatHandler, ConversationState
        from chatbot.moving_models import MovingConversationState, MovingBooking
        
        # Add more detailed logging
        logger.info(f"handle_moving_query called with: company_id={company_id}, session_id={session_id}")
        logger.info(f"Query: '{query}'")
        logger.info(f"History length: {len(history) if history else 0}")
        
        # Quick check for obvious moving-related keywords
        moving_keywords = ["move", "moving", "relocation", "relocate", "shift", "movers", "moving company"]
        is_explicit_moving_query = any(keyword in query.lower() for keyword in moving_keywords)
        logger.info(f"Is explicit moving query: {is_explicit_moving_query}")
        
        # Look for origin/destination pattern in the query (e.g., "from X to Y")
        from_to_pattern = re.search(r'(?:move|moving)?\s+(?:from\s+)([^,]+)(?:\s+to\s+)([^,\.]+)', query.lower())
        has_location_pattern = bool(from_to_pattern)
        logger.info(f"Has location pattern: {has_location_pattern}")
        
        if has_location_pattern:
            logger.info(f"Detected origin: {from_to_pattern.group(1).strip()}")
            logger.info(f"Detected destination: {from_to_pattern.group(2).strip()}")
        
        # Create the handler with default state
        handler = MovingChatHandler(company_id, session_id)
        
        # Look up existing conversation state from memory cache first
        cache_key = (company_id, session_id)
        if cache_key in CONVERSATION_STATE_CACHE:
            logger.info(f"Found cached conversation state for {company_id}:{session_id}")
            cached_state = CONVERSATION_STATE_CACHE[cache_key]
            try:
                # Use the cached state to create the handler
                handler.state = getattr(ConversationState, cached_state['state'])
                handler.collected_info = cached_state['collected_info'] or {}
                handler.estimated_cost = cached_state['estimated_cost']
                logger.info(f"Reconstructed handler from cache with state: {handler.state.name}")
                logger.info(f"Cached collected info: {handler.collected_info}")
            except Exception as cache_error:
                logger.error(f"Error restoring from cached state: {cache_error}")
        
        # If not in cache, try the database
        else:
            try:
                # Make sure we have a clean session before querying
                db.session.rollback()
                
                conv_state = MovingConversationState.query.filter_by(
                    company_id=company_id, 
                    session_id=session_id
                ).first()
                
                if conv_state:
                    logger.info(f"Found existing conversation state in database: {conv_state.state}")
                    # Update handler with stored state
                    try:
                        handler.state = getattr(ConversationState, conv_state.state)
                        handler.collected_info = conv_state.collected_info or {}
                        handler.estimated_cost = conv_state.estimated_cost
                        logger.info(f"Recreated handler with state: {handler.state.name}")
                        logger.info(f"Existing collected info: {handler.collected_info}")
                    except Exception as state_error:
                        logger.error(f"Error setting handler state: {state_error}")
                        # Continue with default handler state
                else:
                    logger.info("No existing conversation state found, using new handler")
            except Exception as e:
                logger.warning(f"Error retrieving conversation state (likely permissions issue): {e}")
                logger.info("Using new handler with default state")
                # Make sure we rollback on error
                try:
                    db.session.rollback()
                except Exception as rollback_error:
                    logger.warning(f"Error rolling back after conversation state error: {rollback_error}")
        
        # Log the current state before processing
        logger.info(f"CURRENT STATE BEFORE PROCESSING: {handler.state.name}")
        
        # Process the message
        logger.info(f"Calling handler.handle_message with query: '{query[:30]}...'")
        response_data = handler.handle_message(query, history)
        response_text = response_data.get('response')
        
        # CRITICAL FIX: Check for phone number input or CONFIRM_BOOKING state
        phone_number_input = False
        
        # First, check if this looks like a phone number by removing formatting characters
        if query:
            # Remove all common phone number formatting characters
            cleaned_query = query.strip().replace('-', '').replace(' ', '').replace('(', '').replace(')', '').replace('+', '').replace('.', '')
            # Check if what remains is just digits of appropriate length for a phone number
            if cleaned_query.isdigit() and 6 <= len(cleaned_query) <= 15:
                logger.warning(f"***** DETECTED PHONE NUMBER INPUT: {query} *****")
                phone_number_input = True
                
        # Also check for obviously incorrect phone number inputs
        if query and query.lower() in ["booking summary?", "summary?", "booking summary", "summary", "?"]:
            logger.warning(f"***** DETECTED INVALID QUERY AS PHONE NUMBER INPUT: {query} *****")
            # This is not a phone number but a query for booking summary
            # We'll handle this by forcing a proper phone number input
            response_text = "I need your phone number to complete the booking. Please provide a valid phone number."
            return response_text
            
        # Check for valid phone number format
        elif query and re.match(r'^\d{6,15}$', query.strip().replace('-', '').replace(' ', '').replace('+', '')):
            logger.info(f"***** DETECTED PHONE NUMBER INPUT: {query} *****")
            phone_number_input = True
            
        # If we just collected a phone number or transitioned to CONFIRM_BOOKING state
        # Force a booking summary instead of premature confirmation
        if (phone_number_input or response_data.get('state') == 'CONFIRM_BOOKING') and 'customer_phone' in handler.collected_info:
            logger.info(f"***** DETECTED CONFIRM_BOOKING TRANSITION AFTER PHONE COLLECTION *****")
            
            # If the response doesn't contain booking summary but has confirmation text
            if (response_text and 
                "booking summary" not in response_text.lower() and 
                "has been successfully booked" in response_text.lower()):
                
                logger.warning(f"***** DETECTED PREMATURE CONFIRMATION - WILL OVERRIDE *****")
                # Set a flag to force a booking summary below
                force_booking_summary = True
            else:
                force_booking_summary = False
                logger.info(f"***** RESPONSE SEEMS CORRECT, NO OVERRIDE NEEDED *****")
        
        logger.info(f"Handler returned state: {response_data.get('state')}")
        # Log state transition if it happened
        if handler.state.name != response_data.get('state'):
            logger.info(f"STATE TRANSITION: {handler.state.name} -> {response_data.get('state')}")
        
        # Safely log response text, handling None case
        if response_text:
            logger.info(f"Handler returned response: '{response_text[:50]}...'")
        else:
            logger.info("Handler returned response: None")
        
        # Only try database operations if we have a valid booking confirmation
        if response_data and response_data.get('booking_confirmed'):
            try:
                # Ensure clean session before creating booking
                db.session.rollback()
                
                logger.info("Creating MovingBooking record in database")
                booking = MovingBooking.from_conversation_data(
                    company_id=company_id,
                    session_id=session_id,
                    collected_info=handler.collected_info,
                    estimated_cost=handler.estimated_cost
                )
                db.session.add(booking)
                try:
                    db.session.commit()
                    logger.info(f"Successfully created booking record with ID: {booking.id}")
                except Exception as commit_error:
                    logger.error(f"Error committing booking: {commit_error}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    db.session.rollback()
            except Exception as booking_error:
                logger.error(f"Could not create booking record: {booking_error}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                try:
                    db.session.rollback()
                except Exception as rollback_error:
                    logger.warning(f"Error rolling back after booking error: {rollback_error}")
        
        # Handle complaint registrations
        elif response_data and response_data.get('complaint_registered'):
            logger.info("Complaint registration detected, would save complaint details here")
            # In a real implementation, you would save the complaint to a database table
            # and potentially trigger notifications to staff
            try:
                # Log the complaint details for now
                complaint_details = response_data.get('complaint_details', {})
                logger.info(f"Complaint registered for {complaint_details.get('customer_name')}")
                logger.info(f"Contact: {complaint_details.get('customer_email')}, {complaint_details.get('customer_phone')}")
                logger.info(f"Details: {complaint_details.get('complaint_details', '')[:100]}...")
                
                # Here you would typically save to a database table
                # For example:
                # complaint = CustomerComplaint(
                #     company_id=company_id,
                #     session_id=session_id,
                #     customer_name=complaint_details.get('customer_name'),
                #     customer_email=complaint_details.get('customer_email'),
                #     customer_phone=complaint_details.get('customer_phone'),
                #     complaint_text=complaint_details.get('complaint_details'),
                #     status='new',
                #     created_at=datetime.utcnow()
                # )
                # db.session.add(complaint)
                # db.session.commit()
            except Exception as complaint_error:
                logger.error(f"Error handling complaint registration: {complaint_error}")
                try:
                    db.session.rollback()
                except Exception as rollback_error:
                    logger.warning(f"Error rolling back after complaint error: {rollback_error}")
        
        # Store the handler state in our memory cache
        cache_value = {
            'state': response_data.get('state'),
            'collected_info': handler.collected_info,
            'estimated_cost': handler.estimated_cost
        }
        CONVERSATION_STATE_CACHE[cache_key] = cache_value
        logger.info(f"Stored conversation state in memory cache: {response_data.get('state')}")
        logger.info(f"Current collected_info in cache: {handler.collected_info}")
        
        # Try to update conversation state in the database, but handle errors gracefully
        try:
            # Ensure clean session before updating state
            db.session.rollback()
            
            # First check if the state exists
            existing_state = MovingConversationState.query.filter_by(
                company_id=company_id, 
                session_id=session_id
            ).first()
            
            if existing_state:
                # Update existing state
                existing_state.state = response_data.get('state')
                existing_state.collected_info = handler.collected_info
                existing_state.estimated_cost = handler.estimated_cost
                existing_state.updated_at = datetime.utcnow()
            else:
                # Create new state
                new_state = MovingConversationState(
                    company_id=company_id,
                    session_id=session_id,
                    state=response_data.get('state'),
                    collected_info=handler.collected_info,
                    estimated_cost=handler.estimated_cost
                )
                db.session.add(new_state)
            
            # Try to commit, but don't fail if we can't
            try:
                db.session.commit()
                logger.info(f"Saved conversation state to database: {response_data.get('state')}")
            except Exception as commit_error:
                logger.error(f"Error committing conversation state: {commit_error}")
                db.session.rollback()
        except Exception as state_error:
            logger.warning(f"Error saving conversation state (likely permissions issue): {state_error}")
            # Make sure we rollback on error
            try:
                db.session.rollback()
            except Exception as rollback_error:
                logger.warning(f"Error rolling back after state error: {rollback_error}")
        
        # Ensure clean session before returning
        try:
            db.session.rollback()
        except Exception as final_rollback_error:
            logger.warning(f"Error in final rollback before returning: {final_rollback_error}")
        
        # CRITICAL OVERRIDE: Force booking summary in any of these cases:
        # 1. We explicitly flagged it above
        # 2. We detected a phone number input and premature confirmation
        # 3. We have the special "_showing_booking_summary" marker in collected_info
        
        # FORCE DETECTION: Check if this is a phone number or if we need to override
        if query and query.lower() in ["booking summary?", "summary?", "booking summary", "summary", "?"]:
            logger.warning(f"***** EMERGENCY OVERRIDE: USER ASKING FOR BOOKING SUMMARY: {query} *****")
            # Force booking summary display
            handler.collected_info['_showing_booking_summary'] = True
            handler.collected_info['_force_booking_summary'] = True
            # Force the state to CONFIRM_BOOKING
            handler.state = ConversationState.CONFIRM_BOOKING
        elif (query and 
            re.match(r'^[\d\-\(\)\s\+\.]{6,20}$', query) and
            'customer_email' in handler.collected_info and 
            'customer_phone' not in handler.collected_info):
            logger.warning(f"***** EMERGENCY OVERRIDE: DETECTED PHONE NUMBER INPUT THAT WASN'T PROCESSED: {query} *****")
            # Store the phone number manually 
            handler.collected_info['customer_phone'] = query.strip()
            logger.warning(f"***** STORED PHONE: {handler.collected_info['customer_phone']} *****")
            # Force booking summary flag
            handler.collected_info['_showing_booking_summary'] = True
            handler.collected_info['_force_booking_summary'] = True
            # Force the state to CONFIRM_BOOKING
            handler.state = ConversationState.CONFIRM_BOOKING
            
        if ('force_booking_summary' in locals() and force_booking_summary) or (
            phone_number_input and 
            response_text and 
            "has been successfully booked" in response_text.lower()) or (
            '_showing_booking_summary' in handler.collected_info and
            handler.collected_info.get('_showing_booking_summary', False)) or (
            "thank you for providing your phone number" in response_text.lower()):
            
            logger.warning("***** CRITICAL OVERRIDE: Detected premature booking confirmation *****")
            logger.warning("***** FORCING BOOKING SUMMARY INSTEAD *****")
            
            # Generate booking summary manually
            origin = handler.collected_info.get('origin', 'Unknown')
            destination = handler.collected_info.get('destination', 'Unknown')
            move_date = handler.collected_info.get('move_date', 'Unknown')
            move_size = handler.collected_info.get('move_size', 'Unknown')
            name = handler.collected_info.get('customer_name', 'Unknown')
            email = handler.collected_info.get('customer_email', 'Unknown')
            phone = handler.collected_info.get('customer_phone', 'Unknown')
            
            # Format additional services
            additional_services = handler.collected_info.get('additional_services', [])
            services_text = ", ".join(additional_services) if additional_services else "None"
            
            if handler.estimated_cost:
                total_cost = handler.estimated_cost.get('total_cost', 0)
                formatted_total = '{:,.2f}'.format(total_cost)
                
                # Extract more cost details if available
                base_rate = handler.estimated_cost.get('base_rate', 0)
                formatted_base = '{:,.2f}'.format(base_rate)
                
                distance_cost = handler.estimated_cost.get('distance_cost', 0)
                formatted_distance = '{:,.2f}'.format(distance_cost)
                
                services_cost = handler.estimated_cost.get('services_cost', 0)
                formatted_services = '{:,.2f}'.format(services_cost)
                
                distance_miles = handler.collected_info.get('distance_miles', 0)
                
                override_summary = (
                    f"📋 **Booking Summary**\n\n"
                    f"**Moving Details:**\n"
                    f"- From: {origin}\n"
                    f"- To: {destination}\n"
                    f"- Date: {move_date}\n"
                    f"- Size: {move_size}\n"
                    f"- Distance: {distance_miles} miles\n"
                    f"- Additional Services: {services_text}\n\n"
                    f"**Customer Information:**\n"
                    f"- Name: {name}\n"
                    f"- Email: {email}\n"
                    f"- Phone: {phone}\n\n"
                    f"**Cost Breakdown:**\n"
                    f"- Base Rate: ${formatted_base}\n"
                    f"- Distance Cost: ${formatted_distance}\n"
                    f"- Additional Services: ${formatted_services}\n"
                    f"- Total Estimated Cost: ${formatted_total}\n\n"
                    f"Is this information correct? Please confirm by replying 'yes' to book your move or 'no' to make changes."
                )
                
                return override_summary
            
        # Persist conversation state to cache for subsequent requests
        try:
            CONVERSATION_STATE_CACHE[(company_id, session_id)] = handler.get_state_dict()
        except Exception as cache_error:
            logger.warning(f"Failed to cache conversation state: {cache_error}")
        
        return response_text
        
    except Exception as e:
        logger.error(f"Error in handle_moving_query: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Try to rollback the session to clean state for next request
        try:
            from core.database import db
            db.session.rollback()
        except Exception as rollback_error:
            logger.warning(f"Error rolling back after general error: {rollback_error}")
        # Fall back to regular chatbot
        return None
