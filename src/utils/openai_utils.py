"""
OpenAI Utilities

Provides functions to interact with OpenAI APIs for:
- Message classification
- Information extraction
- Chatbot conversations
"""

import os
import json
import logging
import openai
from datetime import datetime
import re

# Create a logger
logger = logging.getLogger(__name__)

# Initialize OpenAI client
api_key = os.environ.get("OPENAI_API_KEY")
if api_key:
    openai.api_key = api_key
else:
    logger.warning("OPENAI_API_KEY not set. OpenAI functions will not work.")

def classify_message(message_text):
    """
    Classify a user message into one of several categories specifically for moving companies:
    - general_query: General question about moving companies or services
    - company_info: Questions about the specific company details
    - moving_query: Question about a specific moving request, estimate, or booking
    - complaint: Customer complaint or issue with a moving service
    
    Args:
        message_text (str): The user's message to classify
    
    Returns:
        dict: Classification with category and confidence score
    """
    try:
        # Before calling OpenAI, check for obvious complaint keywords for efficiency
        complaint_keywords = ["complain", "unhappy", "dissatisfied", "disappointed", "issue", "problem", 
                             "terrible", "awful", "bad service", "poor service", "not satisfied", 
                             "unacceptable", "frustrated", "complaint", "wrong", "damaged", "late",
                             "lost my", "missing", "failed to", "never showed", "didn't show up"]
        
        # If we have obvious complaint keywords, return immediately without API call
        if any(keyword in message_text.lower() for keyword in complaint_keywords):
            return {'category': 'complaint', 'confidence': 0.9}
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a message classifier for a moving company's chatbot.
Classify the following message into ONE of these categories:

1. company_info: Questions specifically about company details, history, services offered, or policies.
   Examples: "What is your company's name?", "How long have you been in business?", "Do you offer packing services?"

2. moving_query: Questions about a SPECIFIC moving job, booking, or estimate.
   Examples: "I want to move from Boston to New York", "How much to move a 2-bedroom apartment?", "I need to schedule a move"

3. general_query: General questions about moving processes or advice.
   Examples: "How should I prepare for a move?", "What's the best way to pack dishes?", "What size truck do I need?"
   
4. complaint: Customer expressing dissatisfaction or reporting an issue.
   Examples: "My furniture was damaged", "The movers were late", "No one showed up for my appointment"

Respond ONLY with a JSON object containing 'category' and 'confidence' score (0.0-1.0).
Choose exactly ONE category that best matches the query.
"""},
                {"role": "user", "content": message_text}
            ],
            max_tokens=150,
            temperature=0.1,
        )
        
        # Extract the JSON response
        content = response.choices[0].message["content"]
        
        # Try to parse as JSON
        try:
            classification = json.loads(content)
            if 'category' not in classification:
                classification = {'category': 'general_query', 'confidence': 0.7}
            
            # Log the classification result
            logger.info(f"Classified message as '{classification['category']}' with confidence {classification['confidence']}")
            return classification
        except json.JSONDecodeError:
            # If not valid JSON, extract category using basic parsing
            logger.warning(f"Failed to parse JSON response: {content}")
            if "moving_query" in content.lower():
                return {'category': 'moving_query', 'confidence': 0.8}
            elif "complaint" in content.lower():
                return {'category': 'complaint', 'confidence': 0.8}
            elif "company_info" in content.lower():
                return {'category': 'company_info', 'confidence': 0.8}
            else:
                return {'category': 'general_query', 'confidence': 0.7}
            
    except Exception as e:
        logger.error(f"Error classifying message with OpenAI: {str(e)}")
        # Default to general query when there's an error
        return {'category': 'general_query', 'confidence': 0.5}

def extract_moving_information(message_text, existing_info=None):
    """
    Extract moving-related information from user messages.
    
    Args:
        message_text (str): The user's message to extract info from
        existing_info (dict, optional): Any previously extracted information
        
    Returns:
        dict: Extracted information with origin, destination, move_size, move_date
    """
    # Initialize with existing info or empty dict
    info = existing_info or {}
    
    # Improved direct pattern matching for common moving-related phrases
    improved_match = re.search(r'\bfrom\s+(.+?)(?:\s+and\b|\s+to\b)', message_text, re.IGNORECASE)
    if improved_match:
        origin = improved_match.group(1).strip()
        if not info.get('origin'):
            info['origin'] = origin
            logger.debug(f"Extracted origin: {origin}")
        # Capture destination (e.g., zip code or location after the last 'to')
        dest_matches = re.findall(r'\bto\s+([^,\.]+)', message_text, re.IGNORECASE)
        if dest_matches and not info.get('destination'):
            destination = dest_matches[-1].strip()
            info['destination'] = destination
            logger.debug(f"Extracted destination: {destination}")
    else:
        # Check for specific city names
        cities = ["new york", "los angeles", "chicago", "houston", "phoenix", "philadelphia", 
                 "san antonio", "san diego", "dallas", "san jose", "austin", "jacksonville", 
                 "fort worth", "columbus", "charlotte", "indianapolis", "san francisco", 
                 "seattle", "denver", "boston", "el paso", "detroit", "nashville", "portland", 
                 "memphis", "oklahoma city", "las vegas", "miami", "baltimore", "atlanta",
                 "washington dc", "washington d.c.", "washington"]
        
        # Try to detect simple mentions of cities in context (e.g., "Miami to Dallas")
        city_pattern = '|'.join(cities)
        city_match = re.search(rf'({city_pattern})\s+to\s+({city_pattern})', message_text.lower())
        if city_match:
            logger.debug("Found city to city pattern in message")
            if not info.get('origin'):
                info['origin'] = city_match.group(1).strip()
                logger.debug(f"Extracted origin from city pattern: {info['origin']}")
            
            if not info.get('destination'):
                info['destination'] = city_match.group(2).strip()
                logger.debug(f"Extracted destination from city pattern: {info['destination']}")
        else:
            # Try simpler pattern without "from" keyword (e.g., "New York to California")
            simple_to_pattern = re.search(r'([a-zA-Z\s]+)\s+to\s+([a-zA-Z\s]+)', message_text)
            if simple_to_pattern:
                logger.debug("Found simple to pattern in message")
                potential_origin = simple_to_pattern.group(1).strip()
                potential_destination = simple_to_pattern.group(2).strip()
                
                # Only use this pattern if both look like valid locations (no verbs or prepositions)
                if (len(potential_origin.split()) <= 3 and 
                    len(potential_destination.split()) <= 3 and 
                    not any(word in potential_origin.lower() for word in ['want', 'need', 'like', 'have', 'get']) and
                    not any(word in potential_destination.lower() for word in ['want', 'need', 'like', 'have', 'get'])):
                    
                    if not info.get('origin'):
                        info['origin'] = potential_origin
                        logger.debug(f"Extracted origin from simple pattern: {potential_origin}")
                    
                    if not info.get('destination'):
                        info['destination'] = potential_destination
                        logger.debug(f"Extracted destination from simple pattern: {potential_destination}")
    
    # Extract move size from direct patterns like "X bedroom" or "X-bedroom"
    size_match = re.search(r'(\d+)[\s-]*(bed|bedroom|br)', message_text.lower())
    if size_match and not info.get('move_size'):
        bedrooms = size_match.group(1)
        info['move_size'] = f"{bedrooms}-bedroom"
        logger.debug(f"Extracted move size from pattern: {info['move_size']}")
    
    # Look for studio apartment
    if 'studio' in message_text.lower() and not info.get('move_size'):
        info['move_size'] = 'studio'
        logger.debug("Extracted move size: studio")
    
    try:
        # Define what we're looking for
        system_prompt = """You are an AI assistant for a moving company. 
        Extract the following information from the customer's message:
        1. Origin location (where they're moving from)
        2. Destination location (where they're moving to)
        3. Move size (studio, 1-bedroom, 2-bedroom, 3-bedroom, 4-bedroom, office, car)
        4. Move date (must be a future date)

        Return ONLY a JSON object with these fields: 
        {
            "origin": "extracted origin or null if not found", 
            "destination": "extracted destination or null if not found",
            "move_size": "one of [studio, 1-bedroom, 2-bedroom, 3-bedroom, 4-bedroom, office, car] or null",
            "move_date": "extracted date in YYYY-MM-DD format or null",
            "is_complete": boolean indicating if all fields are present
        }
        
        If you can't confidently extract a piece of information, return null for that field.
        For move_size, map to the closest option in our list.
        For dates, make sure to convert any format (like "31st July 2025" or "July 31, 2025") to YYYY-MM-DD format.
        
        For origin and destination, be careful to distinguish between them correctly. 
        The origin is where they are moving FROM, and the destination is where they are moving TO.
        Look for patterns like "move from X to Y" or "moving from X to Y" to identify origin and destination correctly.
        """
        
        # Add any existing information to the prompt
        context = ""
        if existing_info:
            context = "I already know the following information:\n"
            if 'origin' in existing_info and existing_info['origin']:
                context += f"- Origin: {existing_info['origin']}\n"
            if 'destination' in existing_info and existing_info['destination']:
                context += f"- Destination: {existing_info['destination']}\n"
            if 'move_size' in existing_info and existing_info['move_size']:
                context += f"- Move size: {existing_info['move_size']}\n"
            if 'move_date' in existing_info and existing_info['move_date']:
                context += f"- Move date: {existing_info['move_date']}\n"
            
            system_prompt += "\n" + context + "\nPlease help me extract any missing information from the customer's new message."
        
        # If OpenAI API is not available, use regex-based extraction as fallback
        if not api_key:
            logger.warning("OPENAI_API_KEY not set. Using regex-based extraction as fallback.")
            return _extract_moving_info_fallback(message_text, existing_info)
            
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ],
            max_tokens=200,
            temperature=0.1,
        )
        
        # Extract the JSON response
        content = response.choices[0].message["content"]
        
        # Try to parse as JSON
        try:
            extracted_info = json.loads(content)
            
            # Update existing info with new info, keeping old values if new ones are null
            for key in ['origin', 'destination', 'move_size', 'move_date']:
                if key in extracted_info and extracted_info[key] is not None and extracted_info[key] != "null":
                    info[key] = extracted_info[key]
                elif key not in info:
                    info[key] = None
            
            # For simple responses containing just a number and "bedroom" or "bed"
            # These are common answers to "What size is your home?"
            if not info.get('move_size') and re.search(r'^\s*(\d+)\s*(?:bed(?:room)?s?)\s*$', message_text, re.IGNORECASE):
                match = re.search(r'^\s*(\d+)\s*(?:bed(?:room)?s?)\s*$', message_text, re.IGNORECASE)
                if match:
                    bedrooms = match.group(1)
                    info['move_size'] = f"{bedrooms}-bedroom"
            
            # For simple responses containing just "studio"
            if not info.get('move_size') and re.search(r'^\s*studio\s*$', message_text, re.IGNORECASE):
                info['move_size'] = "studio"
            
            # For simple responses containing just "office"
            if not info.get('move_size') and re.search(r'^\s*office\s*$', message_text, re.IGNORECASE):
                info['move_size'] = "office"
            
            # For simple date responses like "tomorrow" or "next week"
            if not info.get('move_date'):
                date_patterns = {
                    r'(?:^|\s)today(?:$|\s)': 0,
                    r'(?:^|\s)tomorrow(?:$|\s)': 1,
                    r'(?:^|\s)day after tomorrow(?:$|\s)': 2,
                    r'(?:^|\s)next week(?:$|\s)': 7,
                    r'(?:^|\s)next month(?:$|\s)': 30,
                }
                
                for pattern, days_to_add in date_patterns.items():
                    if re.search(pattern, message_text, re.IGNORECASE):
                        from datetime import datetime, timedelta
                        future_date = datetime.now() + timedelta(days=days_to_add)
                        info['move_date'] = future_date.strftime('%Y-%m-%d')
                        break
            
            # If we have a date but it's not in YYYY-MM-DD format, try to convert it
            if info.get('move_date') and not re.match(r'^\d{4}-\d{2}-\d{2}$', info['move_date']):
                try:
                    # Try to parse common date formats
                    date_formats = [
                        '%d %B %Y',       # 31 July 2025
                        '%dst %B %Y',     # 31st July 2025
                        '%dnd %B %Y',     # 22nd July 2025
                        '%drd %B %Y',     # 23rd July 2025
                        '%dth %B %Y',     # 24th July 2025
                        '%B %d, %Y',      # July 31, 2025
                        '%B %dst, %Y',    # July 31st, 2025
                        '%B %dnd, %Y',    # July 22nd, 2025
                        '%B %drd, %Y',    # July 23rd, 2025
                        '%B %dth, %Y',    # July 24th, 2025
                        '%d/%m/%Y',       # 31/07/2025
                        '%m/%d/%Y',       # 07/31/2025
                    ]
                    
                    # Clean up the date string
                    date_str = info['move_date']
                    date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)  # Remove ordinals
                    
                    parsed_date = None
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if parsed_date:
                        info['move_date'] = parsed_date.strftime('%Y-%m-%d')
                    else:
                        # If we can't parse it, keep the original value
                        logger.warning(f"Could not parse date format: {info['move_date']}")
                except Exception as e:
                    logger.error(f"Error parsing date: {str(e)}")
            
            # Check if all required fields are present and valid
            is_complete = all(info.get(key) is not None and info.get(key) != "null" 
                              for key in ['origin', 'destination', 'move_size', 'move_date'])
            
            # Validate move date is in the future
            if info.get('move_date'):
                try:
                    move_date = datetime.strptime(info['move_date'], '%Y-%m-%d')
                    today = datetime.now()
                    if move_date < today:
                        info['move_date'] = None
                        is_complete = False
                except ValueError:
                    info['move_date'] = None
                    is_complete = False
            
            info['is_complete'] = is_complete
            return info
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from OpenAI response: {str(e)}")
            logger.error(f"Raw response: {content}")
            # Return existing info with is_complete=False
            info['is_complete'] = False
            return info
            
    except Exception as e:
        logger.error(f"Error extracting moving information with OpenAI: {str(e)}")
        # Return existing info with is_complete=False
        info['is_complete'] = False
        return info

def get_missing_info_prompt(extracted_info):
    """
    Generate a prompt asking for missing information needed for a moving estimate
    
    Args:
        extracted_info (dict): The information already extracted from the conversation
        
    Returns:
        str: A prompt asking for specific missing information
    """
    missing = []
    
    if not extracted_info.get('origin'):
        missing.append('origin')
    
    if not extracted_info.get('destination'):
        missing.append('destination')
        
    if not extracted_info.get('move_size'):
        missing.append('move_size')
        
    if not extracted_info.get('move_date'):
        missing.append('move_date')
    
    # Create a prompt based on what's missing
    if len(missing) == 0:
        # This shouldn't happen as this function should only be called when info is missing
        return "Thanks for providing all the necessary information! 😊 Can I help you with anything else about your move?"
        
    elif len(missing) == 1:
        # Only one piece of information missing
        missing_item = missing[0]
        
        if missing_item == 'origin':
            return "Where will you be moving from? 🏠"
            
        elif missing_item == 'destination':
            return "Where will you be moving to? 🏙️"
            
        elif missing_item == 'move_size':
            return "What size is your home? (studio, 1-bedroom, 2-bedroom, etc.) 🛋️"
            
        elif missing_item == 'move_date':
            return "When are you planning to move? 📅"
            
    elif len(missing) == 2:
        # Combine two missing items in one question
        if 'origin' in missing and 'destination' in missing:
            return "To prepare your estimate, could you tell me where you'll be moving from and to? 🚚"
            
        if 'move_size' in missing:
            other = next(item for item in missing if item != 'move_size')
            if other == 'origin':
                return "To help with your estimate, what size is your home and where are you moving from? 🏠"
            elif other == 'destination':
                return "To prepare your quote, what size is your home and where are you moving to? 🏙️"
            elif other == 'move_date':
                return "To finalize your estimate, what size is your home and when are you planning to move? 📅"
                
    else:
        # More than two pieces of information missing
        return "To provide an accurate moving estimate, I'll need a few details: where you're moving from, where you're moving to, and the size of your home. 🚚"
    
    # Fallback prompt
    return "I need a bit more information to provide an accurate estimate for your move. Could you please share a few more details? 😊"

def generate_booking_confirmation_prompt(booking_info):
    """
    Generate a confirmation prompt with all the booking details
    
    Args:
        booking_info (dict): The collected booking information
        
    Returns:
        str: A confirmation prompt for booking
    """
    origin = booking_info.get('origin', 'Unknown origin')
    destination = booking_info.get('destination', 'Unknown destination')
    move_size = booking_info.get('move_size', 'Unknown size')
    move_date = booking_info.get('move_date', 'Unknown date')
    
    # Format the date for display if it's in ISO format
    if move_date and move_date.count('-') == 2:
        try:
            from datetime import datetime
            date_obj = datetime.strptime(move_date, "%Y-%m-%d")
            move_date = date_obj.strftime("%B %d, %Y")
        except:
            # If date parsing fails, use as is
            pass
    
    # Get customer info if available
    customer_name = booking_info.get('customer_name', 'Unknown')
    customer_email = booking_info.get('customer_email', 'Unknown')
    customer_phone = booking_info.get('customer_phone', 'Unknown')
    
    # Get additional services
    additional_services = booking_info.get('additional_services', [])
    services_text = ""
    if additional_services:
        services_text = f"Additional services: {', '.join(additional_services)}. "
    
    # Get estimated cost
    estimated_cost = booking_info.get('estimated_cost', {})
    cost_text = ""
    if estimated_cost:
        min_cost = estimated_cost.get('min_cost', 0)
        max_cost = estimated_cost.get('max_cost', 0)
        cost_text = f"Estimated cost: ${min_cost} - ${max_cost}. "
    
    # Create a confirmation message with appropriate formatting and emojis
    return f"📋 Please review your booking details:\n\n🏠 From: {origin}\n🏙️ To: {destination}\n🛋️ Size: {move_size}\n📅 Date: {move_date}\n💰 {cost_text}\n🧰 {services_text}\n\nAre these details correct? Please confirm with 'yes' or let me know what needs to be changed."

def _extract_moving_info_fallback(message_text, existing_info=None):
    """
    Fallback function to extract moving information using regex when OpenAI API is not available.
    
    Args:
        message_text (str): The user's message to extract info from
        existing_info (dict, optional): Any previously extracted information
        
    Returns:
        dict: Extracted information with origin, destination, move_size, move_date
    """
    # Initialize with existing info or empty dict
    info = existing_info or {
        'origin': None,
        'destination': None,
        'move_size': None,
        'move_date': None,
        'is_complete': False
    }
    
    # Check for simple move size responses
    simple_size_match = re.search(r'^\s*(\d+)\s*(?:bed(?:room)?s?)\s*$', message_text, re.IGNORECASE)
    if simple_size_match and not info.get('move_size'):
        bedrooms = simple_size_match.group(1)
        info['move_size'] = f"{bedrooms}-bedroom"
        logger.debug(f"Extracted move size from simple response: {info['move_size']}")
    
    # Check for "studio" response
    if re.search(r'^\s*studio\s*$', message_text, re.IGNORECASE) and not info.get('move_size'):
        info['move_size'] = "studio"
        logger.debug("Extracted move size: studio")
    
    # Check for "office" response
    if re.search(r'^\s*office\s*$', message_text, re.IGNORECASE) and not info.get('move_size'):
        info['move_size'] = "office"
        logger.debug("Extracted move size: office")
    
    # Check for simple date responses
    simple_date_match = False
    date_patterns = {
        r'(?:^|\s)today(?:$|\s)': 0,
        r'(?:^|\s)tomorrow(?:$|\s)': 1,
        r'(?:^|\s)day after tomorrow(?:$|\s)': 2,
        r'(?:^|\s)next week(?:$|\s)': 7,
        r'(?:^|\s)next month(?:$|\s)': 30,
    }
    
    if not info.get('move_date'):
        for pattern, days_to_add in date_patterns.items():
            if re.search(pattern, message_text, re.IGNORECASE):
                from datetime import datetime, timedelta
                future_date = datetime.now() + timedelta(days=days_to_add)
                info['move_date'] = future_date.strftime('%Y-%m-%d')
                simple_date_match = True
                logger.debug(f"Extracted relative date: {info['move_date']}")
                break
    
    # Only proceed with the standard extraction if we haven't matched a simple pattern
    if not simple_size_match and not simple_date_match:
        # Extract origin and destination with regex patterns
        move_pattern = re.search(r'(?:move|moving)\s+from\s+([^,]+)\s+to\s+([^,]+)', message_text, re.IGNORECASE)
        if move_pattern:
            if not info.get('origin'):
                info['origin'] = move_pattern.group(1).strip()
            if not info.get('destination'):
                info['destination'] = move_pattern.group(2).strip()
        else:
            # Try alternative patterns
            if not info.get('origin'):
                origin_match = re.search(r'from\s+([^,]+)(?:,|\s+to)', message_text, re.IGNORECASE)
                if origin_match:
                    info['origin'] = origin_match.group(1).strip()
            
            if not info.get('destination'):
                dest_match = re.search(r'to\s+([^,]+)(?:,|\s+on|\s+a)', message_text, re.IGNORECASE)
                if dest_match:
                    info['destination'] = dest_match.group(1).strip()
        
        # Extract move size (assuming "X bedroom" pattern)
        if not info.get('move_size'):
            size_match = re.search(r'(\d+)[\s-]*(bed|bedroom|br)', message_text, re.IGNORECASE)
            if size_match:
                bedrooms = size_match.group(1)
                info['move_size'] = f"{bedrooms}-bedroom"
        
        # Extract date (assuming "on X" pattern or date format)
        if not info.get('move_date'):
            date_match = re.search(r'on\s+([^,]+\d{4})', message_text, re.IGNORECASE)
            if date_match:
                date_str = date_match.group(1).strip()
                try:
                    # Try to parse the date
                    date_formats = [
                        '%dst %B %Y', '%dnd %B %Y', '%drd %B %Y', '%dth %B %Y',
                        '%d %B %Y', '%B %d %Y', '%B %dst %Y', '%B %dnd %Y',
                        '%B %drd %Y', '%B %dth %Y'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            info['move_date'] = parsed_date.strftime('%Y-%m-%d')
                            break
                        except ValueError:
                            continue
                    
                    # If still not parsed, use a simple approach
                    if not info.get('move_date'):
                        # Extract year
                        year_match = re.search(r'(\d{4})', date_str)
                        if year_match:
                            year = year_match.group(1)
                            
                            # Extract month
                            month_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)', date_str, re.IGNORECASE)
                            if month_match:
                                month = month_match.group(1).lower()
                                month_num = {
                                    'january': '01', 'february': '02', 'march': '03', 'april': '04',
                                    'may': '05', 'june': '06', 'july': '07', 'august': '08',
                                    'september': '09', 'october': '10', 'november': '11', 'december': '12'
                                }[month]
                                
                                # Extract day
                                day_match = re.search(r'(\d+)(?:st|nd|rd|th)?', date_str)
                                if day_match:
                                    day = day_match.group(1).zfill(2)
                                    info['move_date'] = f"{year}-{month_num}-{day}"
                                else:
                                    info['move_date'] = f"{year}-{month_num}-01"  # Default to 1st day
                            else:
                                info['move_date'] = f"{year}-01-01"  # Default to January 1st
                except Exception as e:
                    logger.error(f"Error parsing date: {e}")
    
    # Process simple city/location responses
    if message_text.strip() and not (info.get('origin') or info.get('destination') or simple_size_match or simple_date_match):
        # If the message is just a city or location, check if we need origin or destination
        if len(message_text.strip().split()) <= 3:  # Simple location like "New York" or "San Francisco, CA"
            if not info.get('origin'):
                info['origin'] = message_text.strip()
                logger.debug(f"Assumed simple location as origin: {info['origin']}")
            elif not info.get('destination'):
                info['destination'] = message_text.strip()
                logger.debug(f"Assumed simple location as destination: {info['destination']}")
    
    # Check if all required fields are present
    info['is_complete'] = all(info.get(key) for key in ['origin', 'destination', 'move_size', 'move_date'])
    
    return info

def interpret_user_message(message_text):
    """
    Interpret a user message into intent and slot/value pairs for moving flow.
    Returns a dict with:
      intent: provide_slot | request_estimate | request_booking | correction | general_query | company_info | complaint
      slot: the slot name if applicable, else None
      value: the extracted value for that slot, else None
      raw_query: the original message_text
    """
    # Multi-slot detection for from...to... patterns
    pair_pattern = r'(?:move|moving)?\s+from\s+([^,]+?)\s+to\s+([^,\.]+)'
    pair_match = re.search(pair_pattern, message_text, re.IGNORECASE)
    if pair_match:
        origin = pair_match.group(1).strip()
        destination = pair_match.group(2).strip()
        return {
            'intent': 'provide_slots',
            'slot': None,
            'value': {'origin': origin, 'destination': destination},
            'raw_query': message_text
        }
    # Quick pre-check for corrections (including change/update requests)
    correction_patterns = {
        'customer_email': r'(?:sorry|mistaken|wrong|change|update|correct).*(?:email)',
        'customer_phone': r'(?:sorry|mistaken|wrong|change|update|correct).*(?:phone|number)',
        'customer_name': r'(?:sorry|mistaken|wrong|change|update|correct).*(?:name)',
        'origin': r'(?:change|update|correct).*(?:from|origin)',
        'destination': r'(?:change|update|correct).*(?:to|destination)',
        'move_size': r'(?:change|update|correct).*(?:size|bed|studio|office)',
        'move_date': r'(?:change|update|correct).*(?:date|when)',
    }
    for slot, pattern in correction_patterns.items():
        if re.search(pattern, message_text, re.IGNORECASE):
            return {'intent': 'correction', 'slot': slot, 'value': None, 'raw_query': message_text}

    # Quick pre-check for estimate or booking requests
    if re.search(r'\b(estimate|quote|cost)\b', message_text, re.IGNORECASE):
        return {'intent': 'request_estimate', 'slot': None, 'value': None, 'raw_query': message_text}
    if re.search(r'\b(book|schedule|confirm)\b', message_text, re.IGNORECASE):
        return {'intent': 'request_booking', 'slot': None, 'value': None, 'raw_query': message_text}

    # Slot filling patterns
    slot_patterns = {
        'origin': r'(?:from|origin)\s+([^,]+?)(?=\s+to\b|,|$)',
        'destination': r'(?:to|destination)\s+([^,\.]+)',
        'move_size': r'(\d+)[\s-]*(?:bed|bedroom|br)|studio|office|car',
        'move_date': r'\b(?:today|tomorrow|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})\b',
        'customer_email': r'[\w\.\-]+@[\w\.\-]+\.[A-Za-z]{2,}',
        'customer_phone': r'\+?\d[\d\-\s]{5,}\d',
    }
    for slot, pattern in slot_patterns.items():
        match = re.search(pattern, message_text, re.IGNORECASE)
        if match:
            # group(1) if capturing else full match
            val = match.group(1) if match.lastindex else match.group(0)
            return {'intent': 'provide_slot', 'slot': slot, 'value': val.strip(), 'raw_query': message_text}

    # Fallback to classify_message for broad categories
    classification = classify_message(message_text)
    cat = classification.get('category')
    if cat in ['company_info', 'complaint']:
        return {'intent': cat, 'slot': None, 'value': None, 'raw_query': message_text}
    return {'intent': 'general_query', 'slot': None, 'value': None, 'raw_query': message_text} 