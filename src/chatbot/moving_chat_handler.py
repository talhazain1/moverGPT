"""
Moving Chat Handler

This module handles the conversation flow for moving cost estimation and booking.
It maintains the state of the conversation and progresses through the different stages.
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum, auto
from utils.openai_utils import (
    classify_message, 
    extract_moving_information, 
    get_missing_info_prompt,
    generate_booking_confirmation_prompt,
    interpret_user_message
)
from utils.google_maps_utils import get_distance_between_locations
from companies.models import MovingParameters
from services.email_service import EmailService, apply_template
import re
import os
import traceback
import calendar
import openai

# Create a logger
logger = logging.getLogger(__name__)

class ConversationState(Enum):
    """Enum representing different states in the moving cost conversation"""
    INITIAL = auto()
    COLLECTING_INFO = auto()
    SHOW_ESTIMATE = auto()
    ASK_ADDITIONAL_SERVICES = auto()
    COLLECTING_CUSTOMER_INFO = auto()
    CONFIRM_BOOKING = auto()
    BOOKING_CONFIRMED = auto()
    BOOKING_CANCELLED = auto()
    GENERAL_CHAT = auto()
    COMPLAINT_HANDLING = auto()  # New state for handling complaints

class MovingChatHandler:
    """Class to handle the moving cost estimation and booking conversation flow"""
    
    def __init__(self, company_id, session_id):
        """
        Initialize the MovingChatHandler
        
        Args:
            company_id (int): The ID of the company
            session_id (int): The ID of the chat session
        """
        self.company_id = company_id
        self.session_id = session_id
        self.state = ConversationState.INITIAL
        self.collected_info = {}
        self.estimated_cost = None
        self.missing_fields = []
        
    def handle_message(self, message_text, history=None):
        """
        Process a user message and return a response based on the current state
        
        Args:
            message_text (str): The user's message
            history (list, optional): List of previous messages
            
        Returns:
            dict: Response with text and updated conversation state
        """
        if len(message_text.strip()) < 2:
            return {
                'response': "I didn't understand. Could you please provide more information?",
                'state': self.state.name
            }
        # If already in complaint handling, always process via complaint state
        if self.state == ConversationState.COMPLAINT_HANDLING:
            return self._handle_complaint_state(message_text)
        
        # Unified intent/slot interpretation
        interpretation = interpret_user_message(message_text)
        intent = interpretation.get('intent')
        slot = interpretation.get('slot')
        value = interpretation.get('value')
        # Detect complaints explicitly before any other flow
        complaint_triggers = [
            "complain", "unhappy", "dissatisfied", "disappointed", "issue", "problem",
            "terrible", "awful", "bad service", "poor service", "not satisfied",
            "unacceptable", "frustrated", "complaint", "wrong", "damaged", "late",
            "lost my", "missing", "failed to", "never showed", "didnt show"
        ]
        if (intent == 'complaint' or any(keyword in message_text.lower() for keyword in complaint_triggers)) and self.state != ConversationState.COMPLAINT_HANDLING:
            logger.info(f"Detected complaint message: {message_text[:30]}...")
            self.state = ConversationState.COMPLAINT_HANDLING
            self.collected_info['complaint_info'] = {}
            prompt = (
                "I'm sorry to hear you have a concern. To better assist you, I'll need to collect some information.\n\n"
                "First, could you please tell me your full name?"
            )
            return {'response': prompt, 'state': self.state.name}

        # Fallback: if we're collecting info and user replies with a bare location, fill missing origin/destination
        if self.state == ConversationState.COLLECTING_INFO and slot is None:
            loc = message_text.strip()
            # If origin missing, assume this is origin
            if not self.collected_info.get('origin') and loc:
                self.collected_info['origin'] = loc
                return {'response': "Great. Where are you moving to? 🏙️", 'state': self.state.name}
            # If destination missing, assume this is destination
            if self.collected_info.get('origin') and not self.collected_info.get('destination') and loc:
                self.collected_info['destination'] = loc
                return {'response': "Thanks. What size is your home? (studio, 1-bedroom, etc.) 🛋️", 'state': self.state.name}

        # Handle multi-slot provision for origin and destination together
        if intent == 'provide_slots' and isinstance(value, dict):
            # Capture both origin and destination
            self.collected_info['origin'] = value.get('origin')
            self.collected_info['destination'] = value.get('destination')
            # Transition to collecting info state
            self.state = ConversationState.COLLECTING_INFO
            # Ask for next missing detail (size or date)
            prompt = get_missing_info_prompt(self.collected_info)
            return {'response': prompt, 'state': self.state.name}

        # Handle corrections (e.g., 'I want to change email')
        if intent == 'correction' and slot:
            # Remove the incorrect slot value
            self.collected_info.pop(slot, None)
            # Ask specifically for the corrected slot
            if slot == 'origin':
                prompt = "Okay, where are you moving from now?"
            elif slot == 'destination':
                prompt = "Sure, where are you moving to now?"
            elif slot == 'move_size':
                prompt = "No problem. What size is your home?"
            elif slot == 'move_date':
                prompt = "Got it. When are you planning to move?"
            elif slot == 'customer_name':
                prompt = "Sure—what's your full name?"
            elif slot == 'customer_email':
                prompt = "Sorry about that. Could you please provide your correct email address?"
            elif slot == 'customer_phone':
                prompt = "No problem. What's your phone number so we can reach you?"
            else:
                # Fallback to missing-info for move details
                prompt = get_missing_info_prompt(self.collected_info)
            return {'response': prompt, 'state': self.state.name}

        # Handle slot-provision for moving and customer details
        if intent == 'provide_slot' and slot and value:
            self.collected_info[slot] = value
            # Move flow: ensure both origin and destination are captured first
            if slot == 'origin':
                # Move into collecting info mode
                self.state = ConversationState.COLLECTING_INFO
                if not self.collected_info.get('destination'):
                    return {'response': "Great. Where are you moving to? 🏙️", 'state': self.state.name}
                return {'response': "Got it. What size is your home? (studio, 1-bedroom, etc.) 🛋️", 'state': self.state.name}
            if slot == 'destination':
                # Move into collecting info mode
                self.state = ConversationState.COLLECTING_INFO
                if not self.collected_info.get('origin'):
                    return {'response': "Understood. Where are you moving from? 🏠", 'state': self.state.name}
                return {'response': "Thanks. What size is your home? (studio, 1-bedroom, etc.) 🛋️", 'state': self.state.name}
            # Continue move flow
            if slot == 'move_size':
                return {'response': "Perfect. When are you planning to move? 📅", 'state': self.state.name}
            if slot == 'move_date':
                self.collected_info['is_complete'] = True
                return self._calculate_and_return_estimate()
            # Customer flow: after booking acceptance
            if slot == 'customer_name':
                return {'response': f"Thank you, {value}! 😊 Could you please share your email address so we can send you the booking confirmation?", 'state': self.state.name}
            if slot == 'customer_email':
                return {'response': "Perfect! 📧 Finally, what's your phone number so our team can contact you about your move?", 'state': self.state.name}
            if slot == 'customer_phone':
                self.state = ConversationState.CONFIRM_BOOKING
                return self._generate_booking_summary_with_confirmation()

        # Handle estimate requests
        if intent == 'request_estimate':
            missing = [k for k in ['origin', 'destination', 'move_size', 'move_date'] if not self.collected_info.get(k)]
            if not missing:
                self.collected_info['is_complete'] = True
                return self._calculate_and_return_estimate()
            prompt = get_missing_info_prompt(self.collected_info)
            return {'response': prompt, 'state': self.state.name}

        # Handle booking requests
        if intent == 'request_booking':
            # Ensure estimate is done
            if not self.estimated_cost:
                return self.handle_message('estimate', history)
            # Collect missing customer info
            for field, question in [
                ('customer_name', "What is your full name?"),
                ('customer_email', "Could you please share your email address?"),
                ('customer_phone', "Finally, what's your phone number?"),
            ]:
                if not self.collected_info.get(field):
                    return {'response': question, 'state': self.state.name}
            # All info present: proceed to booking confirmation
            self.state = ConversationState.CONFIRM_BOOKING
            return self._generate_booking_summary_with_confirmation()
        
        # Check for estimate requests first - fallback keyword logic
        estimate_keywords = ["estimate", "cost", "price", "quote", "how much", "pricing"]
        is_estimate_request = any(keyword in message_text.lower() for keyword in estimate_keywords)
        
        # If user is asking for an estimate and we have enough info, calculate it immediately
        if is_estimate_request and self.collected_info.get('origin') and self.collected_info.get('destination') and self.collected_info.get('move_size'):
            logger.info(f"Detected direct request for estimate with sufficient information")
            # Check if we're just missing the date
            if not self.collected_info.get('move_date'):
                # Use a default date (1 month from now) to enable estimate calculation
                future_date = datetime.now() + timedelta(days=30)
                self.collected_info['move_date'] = future_date.strftime('%Y-%m-%d')
                logger.info(f"Using default move date for estimate: {self.collected_info['move_date']}")
            
            # Calculate the estimate
            self.collected_info['is_complete'] = True
            return self._calculate_and_return_estimate()
        
        # Check for date patterns in the message
        date_patterns = [
            # "July 21, 2025" format
            r'(?:on\s+)?(?:the\s+)?([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',
            # "21st July 2025" format
            r'(?:on\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+),?\s+(\d{4})',
            # "07/21/2025" format
            r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})',
        ]

        date_found = False
        valid_date = False
        invalid_date_reason = ""
        
        # Check for relative date keywords like 'today', 'tomorrow', 'this week', 'next week', 'next month'
        lower_text = message_text.lower()
        # Handle specific weekdays like 'next friday', 'next monday', etc.
        weekday_match = re.search(r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', lower_text)
        if weekday_match:
            weekday_str = weekday_match.group(1)
            weekdays = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
            target_weekday = weekdays.index(weekday_str)
            today = datetime.now()
            days_ahead = (target_weekday - today.weekday() + 7) % 7
            # Ensure we get the next occurrence, not today if it matches
            days_ahead = days_ahead if days_ahead != 0 else 7
            date_obj = (today + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
            self.collected_info['move_date'] = date_obj.strftime("%Y-%m-%d")
            date_found = True
            valid_date = True
            logger.info(f"Extracted relative move date: {self.collected_info['move_date']} from weekday keyword input")
        elif any(keyword in lower_text for keyword in ["today", "tomorrow", "this week", "next week", "next month"]):
            try:
                if "today" in lower_text:
                    date_obj = datetime.now()
                elif "tomorrow" in lower_text:
                    date_obj = datetime.now() + timedelta(days=1)
                elif "next week" in lower_text:
                    date_obj = datetime.now() + timedelta(weeks=1)
                elif "this week" in lower_text:
                    date_obj = datetime.now()
                elif "next month" in lower_text:
                    # Calculate same day next month, adjusting for month length
                    year = datetime.now().year
                    month = datetime.now().month + 1
                    if month == 13:
                        month = 1
                        year += 1
                    day = datetime.now().day
                    max_day = calendar.monthrange(year, month)[1]
                    if day > max_day:
                        day = max_day
                    date_obj = datetime(year, month, day)
                # Normalize to start of day
                date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                self.collected_info['move_date'] = date_obj.strftime("%Y-%m-%d")
                date_found = True
                valid_date = True
                logger.info(f"Extracted relative move date: {self.collected_info['move_date']} from keyword input")
            except Exception as e:
                invalid_date_reason = "Couldn't parse the relative date keyword. Please provide a specific date."
                date_found = True
                valid_date = False

        for pattern in date_patterns:
            date_match = re.search(pattern, message_text)
            if date_match:
                date_found = True
                # Try to parse the date
                try:
                    if len(date_match.groups()) == 3:
                        date_obj = None
                        
                        if date_match.group(1).isalpha():  # "July 21, 2025" format
                            month = date_match.group(1)
                            day = date_match.group(2)
                            year = date_match.group(3)
                            try:
                                date_obj = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
                            except ValueError:
                                # Try abbreviated month name
                                try:
                                    date_obj = datetime.strptime(f"{month} {day} {year}", "%b %d %Y")
                                except ValueError:
                                    invalid_date_reason = f"{month} {day} is not a valid date."
                                    logger.warning(f"Invalid date: {month} {day}, {year}")
                        elif date_match.group(2).isalpha():  # "21st July 2025" format
                            day = date_match.group(1)
                            month = date_match.group(2)
                            year = date_match.group(3)
                            try:
                                date_obj = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
                            except ValueError:
                                # Try abbreviated month name
                                try:
                                    date_obj = datetime.strptime(f"{month} {day} {year}", "%b %d %Y")
                                except ValueError:
                                    invalid_date_reason = f"{day} {month} is not a valid date."
                                    logger.warning(f"Invalid date: {day} {month}, {year}")
                        else:  # "07/21/2025" format
                            month = date_match.group(1)
                            day = date_match.group(2)
                            year = date_match.group(3)
                            
                            # Check if day exceeds maximum days in given month
                            try:
                                month_int = int(month)
                                day_int = int(day)
                                year_int = int(year)
                                
                                # Check if the month and day are valid
                                if month_int < 1 or month_int > 12:
                                    invalid_date_reason = f"Month {month_int} is not valid."
                                    logger.warning(f"Invalid month: {month_int}")
                                    continue
                                
                                # Get maximum days for the given month and year
                                max_days = calendar.monthrange(year_int, month_int)[1]
                                
                                if day_int < 1 or day_int > max_days:
                                    month_name = calendar.month_name[month_int]
                                    invalid_date_reason = f"{month_name} only has {max_days} days, but you entered {day_int}."
                                    logger.warning(f"Invalid day: {day_int} for month: {month_int} which has {max_days} days")
                                    continue
                                
                                date_obj = datetime.strptime(f"{month}/{day}/{year}", "%m/%d/%Y")
                            except ValueError as e:
                                invalid_date_reason = f"{month}/{day}/{year} is not a valid date."
                                logger.warning(f"Invalid date format: {month}/{day}/{year} - {e}")
                                continue
                            
                        # If date was successfully parsed
                        if date_obj:
                            # Check if the date is in the future
                            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                            if date_obj >= today:
                                # Store the date in ISO format
                                self.collected_info['move_date'] = date_obj.strftime("%Y-%m-%d")
                                logger.info(f"Extracted valid future move date: {self.collected_info['move_date']}")
                                valid_date = True
                                break
                            else:
                                invalid_date_reason = "The date you provided is in the past. Please provide a future date."
                                logger.warning(f"Past date provided: {date_obj.strftime('%Y-%m-%d')}")
                except Exception as e:
                    invalid_date_reason = "The date format isn't recognized. Please try a format like 'July 21, 2025' or '07/21/2025'."
                    logger.error(f"Error parsing date: {e}")
        
        # If a date was mentioned but invalid, ask for a valid date
        if date_found and not valid_date and 'move_date' in self.collected_info.get('_last_requested_field', ''):
            logger.info(f"Invalid date detected. Reason: {invalid_date_reason}")
            return {
                'response': f"{invalid_date_reason} Please provide a valid future date for your move.",
                'state': self.state.name
            }
        
        # Direct check for moving with locations, regardless of current state
        # This ensures we catch moving queries even if the classifier misses them
        from_to_pattern = re.search(r'(?:move|moving)?\s+(?:from\s+)([^,]+)(?:\s+to\s+)([^,\.]+)', message_text.lower())
        simple_to_pattern = re.search(r'([a-zA-Z\s]+)\s+to\s+([a-zA-Z\s]+)', message_text)
        
        # If we find a direct location pattern, prioritize this as a moving query
        if from_to_pattern or (simple_to_pattern and not any(word in message_text.lower() for word in ['want', 'need', 'how'])):
            if self.state == ConversationState.INITIAL or self.state == ConversationState.GENERAL_CHAT:
                logger.info("Detected direct location pattern, treating as moving query")
                # Extract any information we can get
                self.collected_info = extract_moving_information(message_text, self.collected_info)
                self.state = ConversationState.COLLECTING_INFO
                
                if self.collected_info.get('origin') and self.collected_info.get('destination'):
                    logger.info(f"Found origin ({self.collected_info['origin']}) and destination ({self.collected_info['destination']})")
                    
                    # If we have all the information, calculate the estimate
                    if self.collected_info.get('is_complete'):
                        return self._calculate_and_return_estimate()
                    else:
                        # Ask for missing information, like move size or date
                        prompt = get_missing_info_prompt(self.collected_info)
                        return {
                            'response': prompt,
                            'state': self.state.name
                        }
        
        # Process based on current state
        # Log the current state for debugging, especially important for the CONFIRM_BOOKING transition
        logger.info(f"Processing message in state: {self.state.name}")
        
        # EMERGENCY FIX: Special handling for booking phone numbers during customer info collection
        phone_number_pattern = re.compile(r'^\d{6,15}$')
        stripped_msg = message_text.strip().replace('-', '').replace(' ', '').replace('+', '')
        if phone_number_pattern.match(stripped_msg) and self.state == ConversationState.COLLECTING_CUSTOMER_INFO:
            logger.info(f"EMERGENCY FIX: Detected customer phone number input: {message_text}")
            # Store the phone number for booking
            self.collected_info['customer_phone'] = stripped_msg
            # Transition to confirmation to show booking summary
            self.state = ConversationState.CONFIRM_BOOKING
            self.collected_info['_force_booking_summary'] = True
            return self._generate_booking_summary_with_confirmation()
        
        if self.state == ConversationState.INITIAL:
            # Check for company name questions
            # Special handling for company named "My Moving Journey"
            company_name_patterns = [
                r"what is my moving journey",
                r"who is my moving journey",
                r"tell me about my moving journey",
                r"what.s my moving journey",
                r"my moving journey company"
            ]
            
            if any(re.search(pattern, message_text.lower()) for pattern in company_name_patterns):
                logger.info("Detected question about the company name 'My Moving Journey', not a moving request")
                return {
                    'response': None,  # Let the general FAQ system handle company info questions
                    'state': self.state.name,
                    'category': 'company_info'
                }
            
            # Insert checklist detection
            checklist_keywords = ["checklist", "moving checklist", "check list", "to-do list"]
            if any(keyword in message_text.lower() for keyword in checklist_keywords):
                checklist = (
                    "Here's a moving checklist to help you prepare:\n"
                    "1. Plan your moving date\n"
                    "2. Sort and declutter your belongings\n"
                    "3. Pack non-essential items early\n"
                    "4. Gather packing supplies (boxes, tape, markers)\n"
                    "5. Label boxes by room\n"
                    "6. Notify utilities and change your address\n"
                    "7. Schedule cleaning services for your old home\n"
                    "8. Arrange childcare or pet care for moving day\n"
                    "9. Do a final walkthrough of your old home\n"
                    "10. Confirm details with the moving company\n"
                    "Let me know if you'd like more details on any of these steps!"
                )
                return {
                    'response': checklist,
                    'state': self.state.name
                }

            # Check for direct moving keywords before classification
            moving_keywords = ["move", "moving", "relocation", "relocate", "shift", "movers", "moving company"]
            if any(keyword in message_text.lower() for keyword in moving_keywords):
                # Extract information immediately
                self.collected_info = extract_moving_information(message_text)
                self.state = ConversationState.COLLECTING_INFO
                
                if self.collected_info['is_complete']:
                    # If we have all the information, calculate the estimate
                    return self._calculate_and_return_estimate()
                else:
                    # Ask for missing information
                    prompt = get_missing_info_prompt(self.collected_info)
                    return {
                        'response': prompt,
                        'state': self.state.name
                    }
            
            # Otherwise, proceed with standard classification
            return self._handle_initial_state(message_text)
            
        elif self.state == ConversationState.COLLECTING_INFO:
            # If we're collecting info, we may need context from conversation history
            if history:
                # Look for the last bot message asking about a specific parameter
                last_bot_message = None
                for msg in reversed(history):
                    if msg.get('sender') == 'bot':
                        last_bot_message = msg.get('message', '')
                        break
                
                if last_bot_message:
                    # Check what the bot last asked for and extract that specifically
                    param_mentions = {
                        'origin': ['where you\'re moving from', 'origin', 'moving from', 'where from'],
                        'destination': ['where you\'re moving to', 'destination', 'moving to', 'where to'],
                        'move_size': ['size of your move', 'home size', 'how big', 'how many bedrooms', 'studio', 'bedroom'],
                        'move_date': ['when', 'date', 'what date', 'moving date', 'planned date']
                    }
                    
                    # Check what parameter was being asked about
                    for param, phrases in param_mentions.items():
                        if any(phrase in last_bot_message.lower() for phrase in phrases):
                            logger.debug(f"Last bot message was asking about {param}")
                            
                            # Extract just that parameter from the user's message
                            if param == 'move_size':
                                # Special handling for move size
                                size_pattern = r'(\d+)[\s-]*(bed|bedroom|br)'
                                size_match = re.search(size_pattern, message_text.lower())
                                if size_match:
                                    bedrooms = size_match.group(1)
                                    self.collected_info['move_size'] = f"{bedrooms}-bedroom"
                                    logger.debug(f"Extracted move_size: {self.collected_info['move_size']}")
                                elif 'studio' in message_text.lower():
                                    self.collected_info['move_size'] = "studio"
                                    logger.debug(f"Extracted move_size: studio")
                                elif 'office' in message_text.lower():
                                    self.collected_info['move_size'] = "office"
                                    logger.debug(f"Extracted move_size: office")
                            else:
                                # For other parameters, use the extraction function
                                param_info = extract_moving_information(message_text)
                                if param_info.get(param):
                                    self.collected_info[param] = param_info[param]
                                    logger.debug(f"Extracted {param}: {self.collected_info[param]}")
            
            # Now handle the collecting state with potentially updated information
            return self._handle_collecting_info_state(message_text)
            
        elif self.state == ConversationState.SHOW_ESTIMATE:
            return self._handle_show_estimate_state(message_text)
            
        elif self.state == ConversationState.ASK_ADDITIONAL_SERVICES:
            return self._handle_additional_services_state(message_text)
            
        elif self.state == ConversationState.COLLECTING_CUSTOMER_INFO:
            # After handling customer info collection, make sure to show booking summary
            # rather than prematurely confirming the booking
            response = self._handle_collecting_customer_info_state(message_text)
            # Log the response to ensure it's what we expect
            logger.info(f"Customer info collection response: {response.get('response')[:50]}...")
            return response
            
        elif self.state == ConversationState.CONFIRM_BOOKING:
            return self._handle_confirm_booking_state(message_text)
            
        elif self.state == ConversationState.BOOKING_CONFIRMED or self.state == ConversationState.BOOKING_CANCELLED:
            # Reset the state to initial for new conversation
            self.state = ConversationState.INITIAL
            return self._handle_initial_state(message_text)
        
        elif self.state == ConversationState.COMPLAINT_HANDLING:
            return self._handle_complaint_state(message_text)
        
        # Default to general chat state
        else:
            return self._handle_general_chat_state(message_text)
    
    def _handle_initial_state(self, message_text):
        """
        Handle messages in the INITIAL state
        """
        # Use the OpenAI classifier to determine query type
        classification = classify_message(message_text)
        category = classification['category']
        confidence = classification.get('confidence', 0.0)
        
        logger.info(f"Message classification: {category} with confidence {confidence}")
        
        # Check for direct estimate requests first
        estimate_keywords = ["estimate", "cost", "price", "quote", "how much", "pricing"]
        is_estimate_request = any(keyword in message_text.lower() for keyword in estimate_keywords)
        
        if is_estimate_request:
            logger.info("Detected estimate request, checking if we have enough information")
            # Do we have enough info to calculate?
            if self.collected_info.get('origin') and self.collected_info.get('destination') and self.collected_info.get('move_size') and self.collected_info.get('move_date'):
                # We have everything we need for an estimate
                logger.info("We have enough info for an estimate")
                self.collected_info['is_complete'] = True
                return self._calculate_and_return_estimate()
            else:
                # Move to collecting info state and ask for the first missing piece
                logger.info("Need more info for estimate, moving to COLLECTING_INFO state")
                self.state = ConversationState.COLLECTING_INFO
                prompt = get_missing_info_prompt(self.collected_info)
                return {
                    'response': prompt,
                    'state': self.state.name
                }
        
        # Handle based on the classification result
        if category == 'company_info':
            # Questions about the company should be handled by the FAQ system
            logger.info("Detected company information query, not treating as moving request")
            return {
                'response': None,  # Let the general FAQ system handle company info questions
                'state': self.state.name,
                'category': 'company_info'
            }
            
        elif category == 'general_query':
            # General questions about moving should be handled by the FAQ system
            logger.info("Detected general question about moving, not treating as moving request")
            return {
                'response': None,  # Let the general FAQ system handle general questions
                'state': self.state.name,
                'category': 'general_query'
            }
            
        elif category == 'complaint':
            # Handle complaint flow
            logger.info("Detected complaint, transitioning to complaint handling")
            self.state = ConversationState.COMPLAINT_HANDLING
            
            # Reset any existing complaint info
            if 'complaint_info' in self.collected_info:
                self.collected_info['complaint_info'] = {}
            
            prompt = (
                "I'm sorry to hear you have a concern. To better assist you, I'll need to collect some information.\n\n"
                "First, could you please tell me your full name?"
            )
            
            return {
                'response': prompt,
                'state': self.state.name,
                'category': 'complaint'
            }
            
        elif category == 'moving_query':
            # Process as a moving query - extract information and start collecting details
            logger.info("Detected moving query, extracting information")
            
            # Check for location information in the message
            from_to_pattern = re.search(r'(?:move|moving)?\s+(?:from\s+)([^,]+)(?:\s+to\s+)([^,\.]+)', message_text.lower())
            if from_to_pattern:
                logger.info(f"Found from/to pattern: {from_to_pattern.group(1)} to {from_to_pattern.group(2)}")
                # Initialize with existing info
                self.collected_info = extract_moving_information(message_text, {})
                self.state = ConversationState.COLLECTING_INFO
                
                if self.collected_info.get('is_complete'):
                    # If we have all the information, calculate the estimate
                    return self._calculate_and_return_estimate()
                else:
                    # Ask for missing information
                    prompt = get_missing_info_prompt(self.collected_info)
                    return {
                        'response': prompt,
                        'state': self.state.name
                    }
            else:
                # Start the moving query process without specific location information
                prompt = "I'd be happy to help with your move. To provide an accurate estimate, I'll need some details. First, where are you moving from?"
                self.state = ConversationState.COLLECTING_INFO
                return {
                    'response': prompt,
                    'state': self.state.name
                }
        
        # If we couldn't classify or if it's an unexpected category, 
        # fall back to the general chatbot for a response
        return {
            'response': None,  # Let the main chatbot handle this
            'state': self.state.name,
            'category': category
        }
    
    def _handle_collecting_info_state(self, message_text):
        """
        Handle messages in the COLLECTING_INFO state
        """
        # Update collected info with new message
        old_info = self.collected_info.copy()
        self.collected_info = extract_moving_information(message_text, self.collected_info)
        
        # If no new information was extracted, try again with just the message
        if old_info == self.collected_info:
            additional_info = extract_moving_information(message_text)
            for key, value in additional_info.items():
                if value and value != "null" and key != 'is_complete':
                    # Special handling for move_date
                    if key == 'move_date' and value:
                        # Validate the date is in the future
                        try:
                            date_obj = datetime.strptime(value, "%Y-%m-%d")
                            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                            
                            if date_obj < today:
                                logger.warning(f"Past date extracted: {value}")
                                # Store what we were last asking about
                                self.collected_info['_last_requested_field'] = 'move_date'
                                return {
                                    'response': "The date you provided is in the past. Please provide a future date for your move.",
                                    'state': self.state.name
                                }
                        except ValueError:
                            logger.warning(f"Invalid date format extracted: {value}")
                            # Store what we were last asking about
                            self.collected_info['_last_requested_field'] = 'move_date'
                            return {
                                'response': "That doesn't seem to be a valid date. Please provide a valid future date for your move (e.g., July 21, 2025).",
                                'state': self.state.name
                            }
                            
                    self.collected_info[key] = value
            
            # Recalculate completeness
            self.collected_info['is_complete'] = all(
                self.collected_info.get(key) not in [None, "null", ""] 
                for key in ['origin', 'destination', 'move_size', 'move_date']
            )
        
        # Check if we have all the required information
        if self.collected_info['is_complete']:
            return self._calculate_and_return_estimate()
        else:
            # Ask for missing information
            prompt = get_missing_info_prompt(self.collected_info)
            # Store what we're asking about
            missing_fields = [key for key in ['origin', 'destination', 'move_size', 'move_date'] 
                             if self.collected_info.get(key) in [None, "null", ""]]
            if missing_fields:
                self.collected_info['_last_requested_field'] = missing_fields[0]
            
            return {
                'response': prompt,
                'state': self.state.name
            }
    
    def _calculate_and_return_estimate(self):
        """
        Calculate the cost estimate and return it
        """
        try:
            logger.debug(f"Starting estimate calculation with collected info: {self.collected_info}")
            
            # Check if OpenAI API key is set
            if not os.environ.get("OPENAI_API_KEY"):
                logger.error("OPENAI_API_KEY environment variable not set.")
                # Return a specific error message for missing API key
                return {
                    'response': "I'm sorry, but I can't provide a moving estimate right now due to a configuration issue. Please try again later or contact customer support.",
                    'state': self.state.name,
                    'error': "OpenAI API key not configured"
                }
            
            # Make sure we have all required information
            if not self.collected_info.get('origin'):
                logger.warning("Missing origin in collected info")
                return {
                    'response': "I need to know where you're moving from. Could you please tell me your origin location?",
                    'state': self.state.name
                }
                
            if not self.collected_info.get('destination'):
                logger.warning("Missing destination in collected info")
                return {
                    'response': "I need to know where you're moving to. Could you please tell me your destination?",
                    'state': self.state.name
                }
                
            if not self.collected_info.get('move_size'):
                logger.warning("Missing move size in collected info")
                return {
                    'response': "I need to know the size of your move. Could you tell me if it's a studio, 1-bedroom, 2-bedroom, etc.?",
                    'state': self.state.name
                }
            
            # Get the distance between origin and destination
            try:
                distance_data = get_distance_between_locations(
                    self.collected_info['origin'], 
                    self.collected_info['destination']
                )
                logger.debug(f"Distance data: {distance_data}")
            except Exception as e:
                logger.error(f"Error getting distance data: {e}")
                # Fallback to a direct distance calculation for development
                logger.info("Using fallback distance calculation")
                # Just use a reasonable estimate based on known city pairs
                city_distances = {
                    ('new york', 'los angeles'): 2800,
                    ('new york', 'chicago'): 800,
                    ('new york', 'miami'): 1300,
                    ('new york', 'dallas'): 1500,
                    ('new york', 'boston'): 200,
                    ('los angeles', 'new york'): 2800,
                    ('los angeles', 'chicago'): 2000,
                    ('los angeles', 'miami'): 2700,
                    ('los angeles', 'dallas'): 1400,
                    ('los angeles', 'boston'): 2900,
                    ('chicago', 'new york'): 800,
                    ('chicago', 'los angeles'): 2000,
                    ('chicago', 'miami'): 1400,
                    ('chicago', 'dallas'): 900,
                    ('chicago', 'boston'): 1000,
                    ('miami', 'new york'): 1300,
                    ('miami', 'los angeles'): 2700,
                    ('miami', 'chicago'): 1400,
                    ('miami', 'dallas'): 1300,
                    ('miami', 'boston'): 1500,
                    ('dallas', 'new york'): 1500,
                    ('dallas', 'los angeles'): 1400,
                    ('dallas', 'chicago'): 900,
                    ('dallas', 'miami'): 1300,
                    ('dallas', 'boston'): 1700,
                    ('boston', 'new york'): 200,
                    ('boston', 'los angeles'): 2900,
                    ('boston', 'chicago'): 1000,
                    ('boston', 'miami'): 1500,
                    ('boston', 'dallas'): 1700,
                }
                
                origin = self.collected_info['origin'].lower()
                destination = self.collected_info['destination'].lower()
                
                # Try to find the distance in our hardcoded list
                distance_miles = city_distances.get((origin, destination))
                if not distance_miles:
                    # If not found, use a default reasonable distance
                    distance_miles = 1000  # Default to 1000 miles for development
                
                distance_data = {
                    'distance_miles': distance_miles,
                    'distance_text': f'{distance_miles} mi',
                    'duration_text': f'{int(distance_miles / 60)} hours {int(distance_miles % 60)} mins'
                }
                logger.debug(f"Using fallback distance data: {distance_data}")
            
            # Get the company's moving parameters with proper error handling
            from core.database import db
            params = None
            
            try:
                # Ensure we have a clean transaction state
                db.session.rollback()
                
                params = MovingParameters.query.filter_by(company_id=self.company_id).first()
                if not params:
                    logger.warning(f"No moving parameters found for company_id={self.company_id}, using defaults")
                    params = MovingParameters(company_id=self.company_id)
                else:
                    logger.debug(f"Found moving parameters for company_id={self.company_id}")
            except Exception as e:
                # Handle database errors gracefully
                logger.error(f"Database error while retrieving moving parameters: {e}")
                logger.info("Using default moving parameters due to database error")
                try:
                    db.session.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error rolling back session: {rollback_error}")
                
                # DEVELOPMENT MODE: Try to get parameters from browser localStorage through JavaScript
                try:
                    from flask import request
                    # Check if we're in a web request context with a referer header
                    if request and request.headers.get('Referer', '').endswith('/static/test.html'):
                        logger.info("Detected test page, trying to get company parameters from API")
                        
                        # Instead of trying to access localStorage through files, let's directly call the API
                        # to get the company parameters
                        import requests
                        import json
                        
                        try:
                            # Make an API call to get the company parameters
                            company_id = self.company_id
                            logger.info(f"Attempting to get parameters for company_id: {company_id}")
                            
                            # Get the base URL from the current request
                            if request.host_url:
                                base_url = request.host_url.rstrip('/')
                            else:
                                base_url = "http://localhost:5006"  # Default fallback
                            
                            # Use relative URL for the API endpoint - use the current company endpoint
                            api_url = f"{base_url}/api/companies/moving_parameters"
                            logger.info(f"Making API request to: {api_url}")
                            
                            # Get parameters from the API
                            # Try to use the token from the request if available
                            auth_header = request.headers.get("Authorization")
                            headers = {}
                            if auth_header:
                                headers["Authorization"] = auth_header
                                logger.info("Using authorization header from original request")
                            
                            api_response = requests.get(api_url, headers=headers)
                            
                            if api_response.status_code == 200:
                                api_data = api_response.json()
                                
                                if api_data.get('success'):
                                    logger.info("Successfully retrieved parameters from API")
                                    param_data = api_data.get('parameters', {})
                                    
                                    # Create a parameters object with the values from the API
                                    params = MovingParameters(company_id=self.company_id)
                                    params.base_rate_per_mile = param_data.get('base_rate_per_mile', 1.50)
                                    params.move_size_rates = param_data.get('move_size_rates', {})
                                    params.rate_adjustments = param_data.get('rate_adjustments', {})
                                    params.additional_service_costs = param_data.get('additional_service_costs', {})
                                    
                                    # Verify the parameters were loaded correctly
                                    logger.info(f"Retrieved base_rate_per_mile: {params.base_rate_per_mile}")
                                    logger.info(f"Retrieved move_size_rates: {params.move_size_rates}")
                                    
                                    return self._continue_estimate_calculation(params, self.collected_info['move_size'], distance_data)
                                else:
                                    logger.warning(f"API call was successful but returned error: {api_data.get('error')}")
                            else:
                                logger.warning(f"Failed to retrieve parameters from API. Status code: {api_response.status_code}")
                        
                        except Exception as api_error:
                            logger.warning(f"Error making API request for parameters: {api_error}")
                            logger.warning(f"Error traceback: {traceback.format_exc()}")
                except Exception as browser_error:
                    logger.warning(f"Error trying to access parameters: {browser_error}")
                
                # Create default parameters object if we couldn't get API parameters
                params = MovingParameters(company_id=self.company_id)
            
            # Default rates and adjustments if we couldn't get them from database
            if not hasattr(params, 'move_size_rates') or not params.move_size_rates:
                logger.warning("No move_size_rates found, using defaults")
                params.move_size_rates = {
                    "studio": 320,
                    "1-bedroom": 640,
                    "2-bedroom": 960,
                    "3-bedroom": 1280,
                    "4-bedroom": 1600,
                    "office": 2000,
                    "car": 120
                }
            
            if not hasattr(params, 'base_rate_per_mile') or not params.base_rate_per_mile:
                logger.warning("No base_rate_per_mile found, using default of 1.50")
                params.base_rate_per_mile = 1.50
                
            if not hasattr(params, 'rate_adjustments') or not params.rate_adjustments:
                logger.warning("No rate_adjustments found, using defaults")
                params.rate_adjustments = {
                    "seasonality_rate": 0.10,
                    "rural_location_rate": 0.10,
                    "min_cost_multiplier": 1.1,
                    "max_cost_multiplier": 1.4
                }
            
            # Validate and normalize move size
            move_size = self.collected_info['move_size']
            logger.debug(f"Original move_size: {move_size}")
            
            # Standardize the format (e.g., "2 bedroom" to "2-bedroom")
            move_size = move_size.lower().strip()
            move_size = re.sub(r'(\d+)\s+bed', r'\1-bed', move_size)
            move_size = re.sub(r'(\d+)\s+bedroom', r'\1-bedroom', move_size)
            # Also handle "2 br", "2br", "2-br" formats
            move_size = re.sub(r'(\d+)\s*br', r'\1-bedroom', move_size)
            move_size = re.sub(r'(\d+)-br', r'\1-bedroom', move_size)
            # Handle "two bedroom" format
            number_words = {
                'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
                'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
            }
            for word, number in number_words.items():
                move_size = re.sub(fr'{word}\s+bed', f'{number}-bed', move_size)
                move_size = re.sub(fr'{word}\s+bedroom', f'{number}-bedroom', move_size)
            
            logger.debug(f"Normalized move_size: {move_size}")
            
            # Check if the exact move size exists in the rates
            if move_size not in params.move_size_rates:
                logger.debug(f"Move size '{move_size}' not found in rates, trying to find a match")
                # Try to find closest match
                valid_sizes = list(params.move_size_rates.keys())
                logger.debug(f"Valid move sizes: {valid_sizes}")
                
                # First try direct substring matching
                for valid_size in valid_sizes:
                    if valid_size.lower() in move_size or move_size in valid_size.lower():
                        move_size = valid_size
                        self.collected_info['move_size'] = valid_size
                        logger.debug(f"Found substring match: {valid_size}")
                        break
                else:
                    # If still not found, try to extract the number of bedrooms
                    bedroom_match = re.search(r'(\d+)[- ]bed', move_size)
                    if bedroom_match:
                        num_bedrooms = bedroom_match.group(1)
                        logger.debug(f"Extracted bedroom number: {num_bedrooms}")
                        for valid_size in valid_sizes:
                            if num_bedrooms in valid_size and 'bedroom' in valid_size.lower():
                                move_size = valid_size
                                self.collected_info['move_size'] = valid_size
                                logger.debug(f"Found bedroom number match: {valid_size}")
                                break
                        else:
                            # If still not found, default to closest bedroom size
                            try:
                                num = int(num_bedrooms)
                                move_size = f"{num}-bedroom"
                                logger.debug(f"Constructed move size: {move_size}")
                                if move_size not in params.move_size_rates:
                                    # Find the closest available bedroom size
                                    bedroom_sizes = [int(re.search(r'(\d+)', vs).group(1)) 
                                                   for vs in valid_sizes 
                                                   if re.search(r'(\d+)-bedroom', vs)]
                                    if bedroom_sizes:
                                        closest = min(bedroom_sizes, key=lambda x: abs(x - num))
                                        move_size = f"{closest}-bedroom"
                                        self.collected_info['move_size'] = move_size
                                        logger.debug(f"Found closest bedroom size: {move_size}")
                            except (ValueError, AttributeError) as e:
                                # Default to 1-bedroom if we can't parse the number
                                logger.debug(f"Error parsing bedroom number: {e}, defaulting to 1-bedroom")
                                move_size = "1-bedroom"
                                self.collected_info['move_size'] = "1-bedroom"
                    else:
                        # If no bedroom count found, default to 1-bedroom
                        logger.debug("No bedroom count found, defaulting to 1-bedroom")
                        move_size = "1-bedroom"
                        self.collected_info['move_size'] = "1-bedroom"
            
            # Ensure the move_size is in the rates
            if move_size not in params.move_size_rates:
                logger.debug(f"Final move size '{move_size}' still not in rates, using 1-bedroom as fallback")
                move_size = "1-bedroom"  # Final fallback
                self.collected_info['move_size'] = "1-bedroom"
            
            # Continue with estimate calculation using the validated parameters and move size
            return self._continue_estimate_calculation(params, move_size, distance_data)
            
        except Exception as e:
            logger.error(f"Error calculating estimate: {str(e)}")
            logger.error(traceback.format_exc())
            self.state = ConversationState.GENERAL_CHAT
            return {
                'response': "I'm sorry, I encountered an error calculating your moving estimate. "
                            "Please try again with clearer information about your move.",
                'state': self.state.name
            }
    
    def _continue_estimate_calculation(self, params, move_size, distance_data):
        """
        Continues the estimate calculation after move size validation
        
        Args:
            params: The moving parameters
            move_size: The validated move size
            distance_data: The distance data
            
        Returns:
            dict: Response with estimate information
        """
        try:
            # Get the base cost for the move size
            if move_size not in params.move_size_rates:
                # Get the closest move size
                move_sizes = list(params.move_size_rates.keys())
                # Sort by similarity
                move_sizes.sort(key=lambda x: self._string_similarity(move_size.lower(), x.lower()), reverse=True)
                move_size = move_sizes[0]
                logger.info(f"Move size '{self.collected_info['move_size']}' not found in params, using '{move_size}' instead")
                self.collected_info['move_size'] = move_size
            
            # Get the base cost for this move size
            base_cost = params.move_size_rates.get(move_size, 0)
            logger.info(f"Base cost for '{move_size}': ${base_cost}")
            
            # Calculate distance cost
            # Get base rate per mile from params
            base_rate_per_mile = params.base_rate_per_mile
            logger.info(f"Base rate per mile: ${base_rate_per_mile}")
            
            # Get distance in miles
            distance_miles = distance_data.get('distance_miles', 0)
            logger.info(f"Distance: {distance_miles} miles")
            
            # Calculate distance cost
            distance_cost = distance_miles * base_rate_per_mile
            logger.info(f"Distance cost: ${distance_cost}")
            
            # Create estimate
            min_cost = base_cost + distance_cost
            max_cost = min_cost * 1.2  # 20% buffer for unexpected costs
            
            # Store the cost breakdown components
            self.estimated_cost = {
                'min_cost': round(min_cost, 2),
                'max_cost': round(max_cost, 2),
                'base_rate': round(base_cost, 2),
                'distance_cost': round(distance_cost, 2),
                'services_cost': 0,  # Will be updated if additional services are added
                'adjustments': 0,    # Will be updated based on seasonality, etc.
                'total_cost': round(max_cost, 2)  # Default to max cost until updated
            }
            
            logger.info(f"Calculated estimate: ${min_cost} - ${max_cost}")
            
            # Store estimate breakdown components
            self.estimated_cost['breakdown'] = {
                'base_cost': base_cost,
                'distance_cost': distance_cost,
                'additional_services': {}
            }
            
            # Update the stored collected information
            self.collected_info['is_estimate_calculated'] = True
            self.collected_info['move_size'] = move_size
            self.collected_info['distance_miles'] = distance_miles
            
            # Transition to SHOW_ESTIMATE state
            self.state = ConversationState.SHOW_ESTIMATE
            
            # Format a friendly response
            formatted_min = '{:,.2f}'.format(min_cost)
            formatted_max = '{:,.2f}'.format(max_cost)
            
            origin = self.collected_info['origin']
            destination = self.collected_info['destination']
            
            response = (
                f"📦 Based on your move from {origin} to {destination} for a {move_size} home, "
                f"I estimate the cost would be between ${formatted_min} and ${formatted_max}. "
                f"This includes our base rate of ${base_cost} for a {move_size} move, "
                f"plus ${'{:,.2f}'.format(distance_cost)} for the {distance_miles} mile distance.\n\n"
                f"Would you like to proceed with booking this move?"
            )
            
            return {
                'response': response,
                'state': self.state.name,
                'estimate': self.estimated_cost
            }
            
        except Exception as e:
            logger.error(f"Error in _continue_estimate_calculation: {e}")
            self.state = ConversationState.INITIAL
            return {
                'response': "I'm sorry, I encountered an error calculating your moving estimate. Let's start over. Where are you moving from and to?",
                'state': self.state.name
            }
    
    def _handle_show_estimate_state(self, message_text):
        """
        Handle messages in the SHOW_ESTIMATE state
        """
        # Check if the user wants to proceed with booking
        message_lower = message_text.lower()
        
        # Log the current state and message for debugging
        logger.info(f"In _handle_show_estimate_state, message: '{message_text}', state: {self.state.name}")
        
        # Check for yes/proceed responses
        if any(word in message_lower for word in ['yes', 'yeah', 'yep', 'proceed', 'book', 'ok', 'okay', 'sure']):
            logger.info("User wants to proceed with booking")
            self.state = ConversationState.ASK_ADDITIONAL_SERVICES
            
            # Prompt for additional services
            prompt = """Great! 🎉 Would you like to add any additional services?

1. 📦 Packing services
2. 🗄️ Storage services
3. ✅ Both packing and storage
4. ❌ No additional services"""
            
            return {
                'response': prompt,
                'state': self.state.name
            }
        
        # Check for no/reject responses
        elif any(word in message_lower for word in ['no', 'nope', 'decline', 'cancel', 'stop', 'not', 'too expensive', 'change']):
            logger.info("User rejected the estimate")
            
            # Ask if they want to modify their request or get information about other services
            prompt = "I understand this estimate doesn't work for you. Would you like to modify your move details or learn about our other services?"
            
            return {
                'response': prompt,
                'state': self.state.name
            }
        
        # Check for requests to see more details about the estimate
        elif any(word in message_lower for word in ['details', 'breakdown', 'explain', 'how', 'why', 'understand']):
            logger.info("User requested more details about the estimate")
            
            # Provide a detailed breakdown with the origin, destination, distance, move size, and base costs
            origin = self.collected_info.get('origin', 'Unknown')
            destination = self.collected_info.get('destination', 'Unknown')
            move_date = self.collected_info.get('move_date', 'Unknown')
            move_size = self.collected_info.get('move_size', 'Unknown')
            distance_miles = self.collected_info.get('distance_miles', 0)
            
            # Format cost details from estimated_cost
            base_rate = self.estimated_cost.get('base_rate', 0)
            formatted_base = '{:,.2f}'.format(base_rate)
            
            distance_cost = self.estimated_cost.get('distance_cost', 0)
            formatted_distance = '{:,.2f}'.format(distance_cost)
            
            total_cost = self.estimated_cost.get('total_cost', 0)
            formatted_total = '{:,.2f}'.format(total_cost)
            
            detailed_response = (
                f"📋 **Detailed Move Estimate**\n\n"
                f"**Moving Details:**\n"
                f"- Origin: {origin}\n"
                f"- Destination: {destination}\n"
                f"- Moving Date: {move_date}\n"
                f"- Home Size: {move_size}\n"
                f"- Distance: {distance_miles} miles\n\n"
                f"**Cost Breakdown:**\n"
                f"- Base Rate for {move_size}: ${formatted_base}\n"
                f"- Distance Cost ({distance_miles} miles): ${formatted_distance}\n"
                f"- Total Estimate: ${formatted_total}\n\n"
                f"Would you like to proceed with booking this move?"
            )
            
            return {
                'response': detailed_response,
                'state': self.state.name,
                'estimate': self.estimated_cost
            }
        
        else:
            # Unclear response, ask for clarification
            clarification = "I'm not sure if you want to proceed with this estimate. Would you like to book this move or would you prefer a different option?"
            
            return {
                'response': clarification,
                'state': self.state.name
            }
    
    def _handle_additional_services_state(self, message_text):
        """
        Handle messages in the ASK_ADDITIONAL_SERVICES state
        """
        message_lower = message_text.lower()
        additional_services = []
        
        # Log for debugging
        logger.info(f"In _handle_additional_services_state, message: '{message_text}', state: {self.state.name}")
        
        # Extract additional services from message
        if any(word in message_lower for word in ['1', 'pack', 'packing']):
            additional_services.append('packing')
            logger.info("Adding packing service")
        
        if any(word in message_lower for word in ['2', 'store', 'storage']):
            additional_services.append('storage')
            logger.info("Adding storage service")
        
        if any(word in message_lower for word in ['3', 'both']):
            additional_services = ['packing', 'storage']
            logger.info("Adding both packing and storage services")
        
        # Handle "no" or "none" response
        if (any(word in message_lower for word in ['4', 'no', 'none', 'neither']) or 
            len(message_lower) <= 3):  # Simple "no" response
            logger.info("No additional services requested")
        
        # Store additional services
        self.collected_info['additional_services'] = additional_services
        
        # Update the cost estimate with additional services
        if additional_services:
            # Convert list to dict format for the update method
            services_dict = {service: True for service in additional_services}
            self._update_estimate_with_additional_services(services_dict)
        
        # Move to collecting customer information
        logger.info("Transitioning to COLLECTING_CUSTOMER_INFO state")
        self.state = ConversationState.COLLECTING_CUSTOMER_INFO
        
        # Start by asking for the customer's name
        prompt = "What is your full name?"
        return {
            'response': prompt,
            'state': self.state.name
        }
    
    def _update_estimate_with_additional_services(self, services):
        """
        Update the cost estimate with additional services
        
        Args:
            services (dict or list): Services to add, either as dict {service: bool} or list of service names
        
        Returns:
            float: The additional cost for the services
        """
        try:
            # Get the moving parameters for the company
            params = MovingParameters.query.filter_by(company_id=self.company_id).first()
            if not params:
                logger.error(f"No moving parameters found for company {self.company_id}")
                return 0
            
            # Get move size
            move_size = self.collected_info.get('move_size')
            if not move_size:
                logger.error("Move size not found in collected info")
                return 0
            
            # Calculate additional cost
            additional_cost = 0
            
            # Convert list to dict if needed
            services_dict = services
            if isinstance(services, list):
                services_dict = {service: True for service in services}
            
            # For each service in the parameters
            for service in params.additional_service_costs:
                # Check if this service is selected
                is_selected = False
                
                # If service is in our services dict and is True
                if service in services_dict and services_dict[service]:
                    is_selected = True
                
                # Alternatively, if it matches a key in the dict (for list input)
                elif service in services_dict:
                    is_selected = True
                
                if is_selected and service in params.additional_service_costs:
                    service_cost = params.additional_service_costs[service].get(move_size, 0)
                    additional_cost += service_cost
                    
                    # Add service cost to breakdown
                    if 'breakdown' in self.estimated_cost:
                        if 'additional_services' not in self.estimated_cost['breakdown']:
                            self.estimated_cost['breakdown']['additional_services'] = {}
                        self.estimated_cost['breakdown']['additional_services'][service] = service_cost
            
            # Update the estimated cost
            if additional_cost > 0:
                logger.info(f"Adding ${additional_cost} for additional services: {services}")
                self.estimated_cost['services_cost'] = additional_cost
                self.estimated_cost['min_cost'] += additional_cost
                self.estimated_cost['max_cost'] += additional_cost
                self.estimated_cost['total_cost'] += additional_cost
            
            return additional_cost
            
        except Exception as e:
            logger.error(f"Error updating estimate with additional services: {e}")
            logger.error(traceback.format_exc())
            return 0
    
    def _handle_collecting_customer_info_state(self, message_text):
        """
        Handle messages in the COLLECTING_CUSTOMER_INFO state
        """
        # Import re module at the function level to ensure it's available
        import re
        
        # Log for debugging
        logger.info(f"In _handle_collecting_customer_info_state, message: '{message_text}', state: {self.state.name}")
        logger.info(f"Current collected info: {self.collected_info}")
        
        # Determine which piece of information we're collecting
        if 'customer_name' not in self.collected_info:
            # Store the customer's name
            self.collected_info['customer_name'] = message_text.strip()
            logger.info(f"Collected customer name: {self.collected_info['customer_name']}")
            
            # Ask for email
            prompt = f"Thank you, {self.collected_info['customer_name']}! 😊 Could you please share your email address so we can send you the booking confirmation?"
            return {
                'response': prompt,
                'state': self.state.name
            }
        
        elif 'customer_email' not in self.collected_info:
            # Validate and store the email
            email = message_text.strip()
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if re.match(email_pattern, email):
                self.collected_info['customer_email'] = email
                logger.info(f"Collected customer email: {self.collected_info['customer_email']}")
                
                # Ask for phone number
                prompt = "Perfect! 📧 Finally, what's your phone number so our team can contact you about your move?"
                return {
                    'response': prompt,
                    'state': self.state.name
                }
            else:
                # Invalid email, ask again
                logger.info(f"Invalid email format: {email}")
                prompt = "Hmm, that doesn't look like a valid email address. 🤔 Could you please provide a valid email format? (example: name@example.com)"
                return {
                    'response': prompt,
                    'state': self.state.name
                }
        
        elif 'customer_phone' not in self.collected_info:
            # Store the phone number
            phone_number = message_text.strip()
            # Check if it's a query rather than a phone number
            if phone_number.lower() in ["booking summary?", "summary?", "booking summary", "summary"]:
                logger.warning(f"Received '{phone_number}' instead of a phone number, asking again")
                prompt = "I need your phone number so our team can contact you about your move. Please provide a valid phone number."
                return {
                    'response': prompt,
                    'state': self.state.name
                }
                
            self.collected_info['customer_phone'] = phone_number
            logger.info(f"Collected customer phone: {self.collected_info['customer_phone']}")
            
            # Validate phone number format - just a basic check
            if not re.match(r'^\d{6,15}$', phone_number.replace('-', '').replace(' ', '').replace('+', '')):
                logger.warning(f"Phone number format may be invalid: {phone_number}")
                # We'll still proceed, but log the warning
            
            # EMERGENCY FIX: MUST show booking summary after phone collection
            logger.info(f"***** EMERGENCY FIX: FORCING BOOKING SUMMARY AFTER PHONE COLLECTION *****")
            logger.info(f"***** BYPASSING NORMAL FLOW TO ENSURE SUMMARY SHOWS *****")
            
            # Don't go to BOOKING_CONFIRMED state, stay in CONFIRM_BOOKING to ensure summary
            self.state = ConversationState.CONFIRM_BOOKING
            
            # Force the booking summary to show by setting a marker
            self.collected_info['_showing_booking_summary'] = True
            self.collected_info['_force_booking_summary'] = True
            self.collected_info['_skip_confirmation'] = False
            
            # CRITICAL FIX: Use the helper method to generate a consistent booking summary
            # This significantly reduces the risk of having different logic in different places
            return self._generate_booking_summary_with_confirmation()
        
        else:
            # This shouldn't happen in normal flow, but handle it just in case
            logger.warning("All customer information already collected, moving to confirmation")
            self.state = ConversationState.CONFIRM_BOOKING
            
            # Force the booking summary to show by setting a marker
            self.collected_info['_showing_booking_summary'] = True
            self.collected_info['_force_booking_summary'] = True
            
            # Use the helper method to generate a consistent booking summary
            return self._generate_booking_summary_with_confirmation()
    
    def _handle_confirm_booking_state(self, message_text):
        """
        Handle messages when the user is asked to confirm their booking
        """
        logger.info(f"Handling message in CONFIRM_BOOKING state: {message_text}")
        
        # Retrieve necessary info from self.collected_info with defaults
        customer_name = self.collected_info.get('customer_name', 'Valued Customer')
        origin = self.collected_info.get('origin', 'your origin')
        destination = self.collected_info.get('destination', 'your destination')
        move_date = self.collected_info.get('move_date', 'the scheduled date')
        
        # Format the date for better display if it's in ISO format (YYYY-MM-DD)
        if move_date and move_date.count('-') == 2:
            try:
                date_obj = datetime.strptime(move_date, "%Y-%m-%d")
                move_date = date_obj.strftime("%B %d, %Y")  # Format as "June 30, 2025"
                logger.info(f"Formatted date for booking confirmation: {move_date}")
            except Exception as e:
                logger.warning(f"Error formatting date in confirmation: {e}")
        
        move_size = self.collected_info.get('move_size', 'Unknown')
        additional_services = self.collected_info.get('additional_services', [])
        services_text = ", ".join(additional_services) if additional_services else "no additional"
        distance_miles = self.collected_info.get('distance_miles', 0)

        # Retrieve and format cost details from self.estimated_cost
        formatted_base = "N/A"
        formatted_distance = "N/A"
        formatted_services = "N/A"
        formatted_total = "N/A"

        if self.estimated_cost:
            base_rate = self.estimated_cost.get('base_rate', 0)
            formatted_base = '{:,.2f}'.format(base_rate)
            
            dist_cost = self.estimated_cost.get('distance_cost', 0)
            formatted_distance = '{:,.2f}'.format(dist_cost)
            
            serv_cost = self.estimated_cost.get('services_cost', 0)
            formatted_services = '{:,.2f}'.format(serv_cost)
            
            total_cost = self.estimated_cost.get('total_cost', 0)
            formatted_total = '{:,.2f}'.format(total_cost)

        # Check for confirmation
        positive_responses = ["yes", "confirm", "ok", "okay", "sure", "proceed", "book it", "do it", "sounds good", "looks good", "correct"]
        if any(word in message_text.lower() for word in positive_responses):
            logger.info("User confirmed booking, transitioning to BOOKING_CONFIRMED")
            self.state = ConversationState.BOOKING_CONFIRMED
            
            # Generate a booking reference
            booking_ref = f"MOV-{self.session_id}-{datetime.now().strftime('%Y%m%d')}"
            logger.info(f"Generated booking reference: {booking_ref}")
            
            # Add booking reference to collected info for database storage
            self.collected_info['booking_reference'] = booking_ref
            
            # Send confirmation emails to both customer and staff
            logger.info("Attempting to send confirmation emails to both customer and staff...")
            email_sent = self._send_confirmation_emails(booking_ref)
            logger.info(f"Email sending result: {email_sent}")
            
            # If primary email method fails, try alternative method
            if not email_sent:
                logger.warning("Primary email method failed, trying alternative email method...")
                alt_email_sent = self._send_alternative_emails(booking_ref)
                if alt_email_sent:
                    logger.info("Alternative email method succeeded")
                    email_sent = True
                else:
                    logger.error("Both primary and alternative email methods failed")
                    
            # Generate a friendly confirmation response with booking reference
            confirmation_text = (
                f"Thank you, {customer_name}! 📱 Your move from {origin} to {destination} on {move_date}, for a {move_size} home with {services_text} services has been successfully booked.\n"
                "\n"
                f"**Booking Reference:** #{booking_ref}\n"
                "\n"
                "**Moving Details:**\n"
                f"- From: {origin}\n"
                f"- To: {destination}\n"
                f"- Date: {move_date}\n"
                f"- Size: {move_size}\n"
                f"- Distance: {distance_miles} miles\n"
                f"- Additional Services: {services_text}\n"
                "\n"
                "**Cost Breakdown:**\n"
                f"- Base Rate: ${formatted_base}\n"
                f"- Distance Cost: ${formatted_distance}\n"
                f"- Additional Services: ${formatted_services}\n"
                f"- Total Cost: ${formatted_total}\n"
            )
            
            return {
                'response': confirmation_text,
                'state': self.state.name,
                'booking_confirmed': True,
                'booking_details': self.collected_info,
                'estimate': self.estimated_cost
            }
        
        # Handle negative responses
        negative_responses = ["no", "nope", "wrong", "incorrect", "change"]
        if any(word in message_text.lower() for word in negative_responses):
            logger.info("User rejected booking details, transitioning to INITIAL")
            self.state = ConversationState.INITIAL
            
            prompt = "I understand you'd like to make some changes. 👍 Let's start fresh. Where are you moving from and to, and what size is your home?"
            
            return {
                'response': prompt,
                'state': self.state.name
            }
        
        # Default to general chat state
        else:
            logger.info("Unclear confirmation response, asking for clarification")
            prompt = "I'm not sure if you want to confirm these booking details. 🤔 Please respond with 'yes' to confirm or 'no' to make changes."
            
            return {
                'response': prompt,
                'state': self.state.name
            }
    
    def _send_confirmation_emails(self, booking_ref):
        """
        Send confirmation emails to both the customer and staff.
        
        Args:
            booking_ref (str): The booking reference number
        
        Returns:
            bool: True if emails were sent successfully, False otherwise
        """
        try:
            logger.info(f"Attempting to send confirmation emails for booking {booking_ref}")
            
            # Debug - show the full collected information to check data availability
            logger.info(f"All collected info: {self.collected_info}")
            logger.info(f"Estimated cost info: {self.estimated_cost}")
            
            # Get email configuration with detailed error handling
            email_config = self._get_email_config()
            if not email_config:
                logger.error("Failed to get email configuration")
                return False
                
            logger.info(f"Email configuration retrieved: {email_config.get('smtp', {}).get('server')}")
            
            # Check if SMTP configuration exists and has all required fields
            smtp_config = email_config.get('smtp', {})
            if not smtp_config:
                logger.warning("No SMTP configuration found in company parameters")
                return False
                
            required_smtp_fields = ['server', 'port', 'username', 'password']
            missing_fields = [field for field in required_smtp_fields if not smtp_config.get(field)]
            if missing_fields:
                logger.warning(f"Missing required SMTP fields: {missing_fields}")
                return False
            
            # Check for required email templates with detailed logging
            if not email_config.get('staff_email_template'):
                logger.warning("Staff email template not configured")
                return False
                
            if not email_config.get('customer_email_template'):
                logger.warning("Customer email template not configured")
                return False
            
            # Prepare data for template replacements
            booking_data = self.collected_info.copy()
            booking_data['booking_reference'] = booking_ref
            
            # Add estimated costs to the template data
            if self.estimated_cost:
                booking_data['base_rate'] = self.estimated_cost.get('base_rate', 0)
                booking_data['distance_cost'] = self.estimated_cost.get('distance_cost', 0)
                booking_data['services_cost'] = self.estimated_cost.get('services_cost', 0)
                booking_data['adjustments'] = self.estimated_cost.get('adjustments', 0)
                booking_data['total_cost'] = self.estimated_cost.get('total_cost', 0)
                
                # Format cost values for template
                for cost_field in ['base_rate', 'distance_cost', 'services_cost', 'adjustments', 'total_cost']:
                    if cost_field in booking_data and booking_data[cost_field]:
                        booking_data[cost_field] = '{:,.2f}'.format(booking_data[cost_field])
            
            # Add distance_miles if not present
            if 'distance_miles' not in booking_data and self.collected_info.get('distance_miles'):
                booking_data['distance_miles'] = self.collected_info.get('distance_miles')
            elif 'distance_miles' not in booking_data:
                booking_data['distance_miles'] = "Unknown"
            
            # Format additional services
            services_list = []
            if 'additional_services' in booking_data and booking_data['additional_services']:
                if isinstance(booking_data['additional_services'], list):
                    services_list = booking_data['additional_services']
                elif isinstance(booking_data['additional_services'], dict):
                    for service, included in booking_data['additional_services'].items():
                        if included:
                            services_list.append(service.capitalize())
                else:
                    # Handle string case
                    services_list = [str(booking_data['additional_services'])]
            
            booking_data['additional_services'] = ", ".join(services_list) if services_list else "None"
            
            # Ensure all required fields have at least default values
            required_fields = ['customer_name', 'customer_email', 'customer_phone', 'origin', 
                              'destination', 'move_date', 'move_size']
            
            for field in required_fields:
                if field not in booking_data or not booking_data[field]:
                    booking_data[field] = f"Not specified"
                    logger.warning(f"Missing required field for email template: {field}")
            
            # Check for customer email
            customer_email = booking_data.get('customer_email')
            if not customer_email or customer_email == "Not specified":
                logger.warning("No customer email address available for sending confirmation")
                return False
            
            # Get staff email from configuration
            staff_email = smtp_config.get('staff_email')
            if not staff_email:
                logger.warning("No staff email address configured")
                return False
            
            # Create an EmailService instance with SMTP configuration
            try:
                # Try multiple import paths to handle different project structures
                try:
                    from services.email_service import EmailService, apply_template
                except ImportError:
                    try:
                        from src.services.email_service import EmailService, apply_template
                    except ImportError:
                        from backend.src.services.email_service import EmailService
                
                email_service = EmailService(smtp_config)
                logger.info("EmailService created successfully")
            except Exception as e:
                logger.error(f"Error creating EmailService: {e}")
                logger.error(traceback.format_exc())
                return False
            
            # Process email templates with booking data
            staff_subject = email_config.get('staff_email_subject', f"New Booking Confirmed - {booking_ref}")
            
            # Define apply_template function locally in case of import issues
            def local_apply_template(template, data):
                if not template:
                    return ""
                    
                result = template
                for key, value in data.items():
                    placeholder = f"{{{{{key}}}}}"
                    if value is None:
                        value = ""
                    result = result.replace(placeholder, str(value))
                
                return result
            
            # Use local function to ensure templates are processed correctly
            template_processor = apply_template if 'apply_template' in locals() or 'apply_template' in globals() else local_apply_template
            
            processed_staff_subject = template_processor(staff_subject, booking_data)
            
            staff_template = email_config.get('staff_email_template')
            processed_staff_template = template_processor(staff_template, booking_data)
            
            customer_template = email_config.get('customer_email_template')
            processed_customer_template = template_processor(customer_template, booking_data)
            
            # Log email details for debugging
            logger.info(f"Staff email will be sent to: {staff_email}")
            logger.info(f"Customer email will be sent to: {customer_email}")
            
            # Log the processed templates (first 100 chars)
            logger.info(f"Processed staff template (first 100 chars): {processed_staff_template[:100]}...")
            logger.info(f"Processed customer template (first 100 chars): {processed_customer_template[:100]}...")
            
            # Send the emails
            try:
                # Prepare email data
                staff_email_data = {
                    "to": staff_email,
                    "subject": processed_staff_subject,
                    "body": processed_staff_template
                }
                
                customer_email_data = {
                    "to": customer_email,
                    "subject": f"Your Moving Quote Confirmation - {booking_ref}",
                    "body": processed_customer_template
                }
                
                result = email_service.send_emails(staff_email_data, customer_email_data)
                logger.info(f"Email sending result: {result}")
                
                if result.get('success'):
                    logger.info(f"Successfully sent confirmation emails for booking {booking_ref}")
                    return True
                else:
                    logger.error(f"Failed to send some or all emails: {result}")
                    # Check individual results
                    staff_result = result.get('staff_email', {})
                    customer_result = result.get('customer_email', {})
                    
                    logger.error(f"Staff email result: {staff_result}")
                    logger.error(f"Customer email result: {customer_result}")
                    
                    # Return true if at least one email was sent successfully
                    if staff_result.get('success') or customer_result.get('success'):
                        logger.info("At least one email was sent successfully")
                        return True
                        
                    return False
            except Exception as e:
                logger.error(f"Exception during email sending: {e}")
                logger.error(traceback.format_exc())
                return False
            
        except Exception as e:
            logger.error(f"Error sending confirmation emails: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _send_alternative_emails(self, booking_ref):
        """
        Alternative email sending method as a backup if the primary method fails.
        Uses hardcoded SMTP settings to ensure emails are sent.
        
        Args:
            booking_ref (str): The booking reference number
        
        Returns:
            bool: True if emails were sent successfully, False otherwise
        """
        try:
            logger.info(f"Using alternative email method for booking {booking_ref}")
            
            # Hardcoded backup SMTP settings
            backup_smtp = {
                "server": "smtp.gmail.com",
                "port": 587,
                "username": "info@movergpt.com",
                "password": "squx iyum vgaw yqhv",  # Note: Use app password for Gmail
                "staff_email": "jackdev24code@gmail.com"
            }
            
            # Prepare data for template replacements
            booking_data = self.collected_info.copy()
            booking_data['booking_reference'] = booking_ref
            
            # Add estimated costs to the template data
            if self.estimated_cost:
                booking_data['base_rate'] = self.estimated_cost.get('base_rate', 0)
                booking_data['distance_cost'] = self.estimated_cost.get('distance_cost', 0)
                booking_data['services_cost'] = self.estimated_cost.get('services_cost', 0)
                booking_data['adjustments'] = self.estimated_cost.get('adjustments', 0)
                booking_data['total_cost'] = self.estimated_cost.get('total_cost', 0)
                
                # Format cost values for template
                for cost_field in ['base_rate', 'distance_cost', 'services_cost', 'adjustments', 'total_cost']:
                    if cost_field in booking_data and booking_data[cost_field]:
                        booking_data[cost_field] = '{:,.2f}'.format(booking_data[cost_field])
            
            # Format additional services
            services_list = []
            if 'additional_services' in booking_data and booking_data['additional_services']:
                if isinstance(booking_data['additional_services'], list):
                    services_list = booking_data['additional_services']
                elif isinstance(booking_data['additional_services'], dict):
                    for service, included in booking_data['additional_services'].items():
                        if included:
                            services_list.append(service.capitalize())
                else:
                    services_list = [str(booking_data['additional_services'])]
            
            booking_data['additional_services'] = ", ".join(services_list) if services_list else "None"
            
            # Customer email content
            customer_email = booking_data.get('customer_email')
            if not customer_email:
                logger.warning("No customer email available for sending confirmation")
                return False
            
            # Simple email templates
            customer_template = f"""Dear {booking_data.get('customer_name', 'Customer')},

Thank you for requesting a moving quote with us!

Here are the details of your request:
- From: {booking_data.get('origin', 'Unknown')}
- To: {booking_data.get('destination', 'Unknown')}
- Moving Date: {booking_data.get('move_date', 'Unknown')}
- Move Size: {booking_data.get('move_size', 'Unknown')}
- Additional Services: {booking_data.get('additional_services', 'None')}

Your estimated cost is ${booking_data.get('total_cost', '0.00')}.
Booking Reference: {booking_ref}

We will contact you shortly to confirm your booking. If you have any questions, please reply to this email or call us.

Thank you for choosing us!

Best regards,
The Moving Team
info@movergpt.com"""

            staff_template = f"""New Moving Request

Booking Reference: {booking_ref}

Customer Information:
- Name: {booking_data.get('customer_name', 'Unknown')}
- Email: {booking_data.get('customer_email', 'Unknown')}
- Phone: {booking_data.get('customer_phone', 'Unknown')}

Moving Details:
- From: {booking_data.get('origin', 'Unknown')}
- To: {booking_data.get('destination', 'Unknown')}
- Moving Date: {booking_data.get('move_date', 'Unknown')}
- Move Size: {booking_data.get('move_size', 'Unknown')}
- Distance: {booking_data.get('distance_miles', 'Unknown')} miles
- Additional Services: {booking_data.get('additional_services', 'None')}

Cost Breakdown:
- Base Rate: ${booking_data.get('base_rate', '0.00')}
- Distance Cost: ${booking_data.get('distance_cost', '0.00')}
- Services Cost: ${booking_data.get('services_cost', '0.00')}
- Total Cost: ${booking_data.get('total_cost', '0.00')}

Please contact the customer as soon as possible to confirm the booking."""

            try:
                # Use the EmailService but with backup SMTP settings
                from services.email_service import EmailService
            except ImportError:
                try:
                    from src.services.email_service import EmailService
                except ImportError:
                    from backend.src.services.email_service import EmailService
            
            # Create EmailService with backup settings
            email_service = EmailService(backup_smtp)
            
            # Prepare and send emails
            staff_email_data = {
                "to": backup_smtp["staff_email"],
                "subject": f"New Booking Confirmed - {booking_ref}",
                "body": staff_template
            }
            
            customer_email_data = {
                "to": customer_email,
                "subject": f"Your Moving Quote Confirmation - {booking_ref}",
                "body": customer_template
            }
            
            # Send both emails
            result = email_service.send_emails(staff_email_data, customer_email_data)
            logger.info(f"Alternative email result: {result}")
            
            if result.get('success'):
                logger.info(f"Alternative email method succeeded for booking {booking_ref}")
                return True
            else:
                # Try sending emails individually as a last resort
                staff_sent = email_service.send_email(staff_email_data.get('to'), 
                                                   staff_email_data.get('subject'), 
                                                   staff_email_data.get('body'))
                
                customer_sent = email_service.send_email(customer_email_data.get('to'), 
                                                     customer_email_data.get('subject'), 
                                                     customer_email_data.get('body'))
                
                logger.info(f"Last resort email results - Staff: {staff_sent}, Customer: {customer_sent}")
                return staff_sent or customer_sent
        
        except Exception as e:
            logger.error(f"Error in alternative email method: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_general_chat_state(self, message_text):
        """
        Handle messages in the GENERAL_CHAT state
        """
        message_lower = message_text.lower()
        
        # Check if user is asking about booking details
        if any(phrase in message_lower for phrase in ['details', 'my booking', 'move details', 'my move', 'booking info']):
            # Check if we have booking information
            if 'origin' in self.collected_info and 'destination' in self.collected_info and 'move_date' in self.collected_info:
                logger.info("User requesting booking details in general chat state")
                
                # Format a comprehensive summary of all collected details
                origin = self.collected_info.get('origin', 'Unknown')
                destination = self.collected_info.get('destination', 'Unknown')
                move_date = self.collected_info.get('move_date', 'Unknown')
                
                # Format the date for better display if it's in ISO format (YYYY-MM-DD)
                if move_date and move_date.count('-') == 2:
                    try:
                        date_obj = datetime.strptime(move_date, "%Y-%m-%d")
                        move_date = date_obj.strftime("%B %d, %Y")  # Format as "June 30, 2025"
                        logger.info(f"Formatted date for general chat display: {move_date}")
                    except Exception as e:
                        logger.warning(f"Error formatting date in general chat: {e}")
                
                move_size = self.collected_info.get('move_size', 'Unknown')
                distance_miles = self.collected_info.get('distance_miles', 0)
                
                # Format additional services
                additional_services = self.collected_info.get('additional_services', [])
                services_text = ", ".join(additional_services) if additional_services else "None"
                
                # Customer details
                name = self.collected_info.get('customer_name', 'Unknown')
                email = self.collected_info.get('customer_email', 'Unknown')
                phone = self.collected_info.get('customer_phone', 'Unknown')
                
                # Format cost details with breakdown
                if self.estimated_cost:
                    base_rate = self.estimated_cost.get('base_rate', 0)
                    formatted_base = '{:,.2f}'.format(base_rate)
                    
                    distance_cost = self.estimated_cost.get('distance_cost', 0)
                    formatted_distance = '{:,.2f}'.format(distance_cost)
                    
                    services_cost = self.estimated_cost.get('services_cost', 0)
                    formatted_services = '{:,.2f}'.format(services_cost)
                    
                    total_cost = self.estimated_cost.get('total_cost', 0)
                    formatted_total = '{:,.2f}'.format(total_cost)
                    
                    booking_ref = self.collected_info.get('booking_reference', 'Not yet confirmed')
                    
                    # Create a detailed booking summary
                    if 'booking_reference' in self.collected_info:
                        # This is a confirmed booking
                        booking_summary = (
                            f"Here are your confirmed booking details:\n\n"
                            f"**Booking Reference:** #{booking_ref}\n\n"
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
                            f"- Total Cost: ${formatted_total}\n\n"
                            f"If you need to make any changes to your booking, please contact our support team."
                        )
                    else:
                        # This is an unconfirmed estimate
                        booking_summary = (
                            f"Here are your moving estimate details:\n\n"
                            f"**Moving Details:**\n"
                            f"- From: {origin}\n"
                            f"- To: {destination}\n"
                            f"- Date: {move_date}\n"
                            f"- Size: {move_size}\n"
                            f"- Distance: {distance_miles} miles\n"
                            f"- Additional Services: {services_text}\n\n"
                            f"**Cost Breakdown:**\n"
                            f"- Base Rate: ${formatted_base}\n"
                            f"- Distance Cost: ${formatted_distance}\n"
                            f"- Additional Services: ${formatted_services}\n"
                            f"- Total Estimated Cost: ${formatted_total}\n\n"
                            f"Would you like to proceed with booking this move?"
                        )
                    
                    # Move to confirmation state if not confirmed yet
                    if 'booking_reference' not in self.collected_info and 'customer_name' in self.collected_info:
                        self.state = ConversationState.CONFIRM_BOOKING
                    
                    return {
                        'response': booking_summary,
                        'state': self.state.name
                    }
                    
            # No booking information available
            return {
                'response': "I don't have any booking details for you yet. Would you like to get a moving quote? Just let me know where you're moving from and to.",
                'state': self.state.name
            }
        
        # Return None to let the main chatbot handle this
        return {
            'response': None,
            'state': self.state.name
        }
    
    def _handle_complaint_state(self, message_text):
        """
        Handle messages in the COMPLAINT_HANDLING state
        """
        # If we're in complaint handling state, we need to collect:
        # 1. Customer name
        # 2. Email address
        # 3. Phone number
        # 4. Complaint details
        
        # Initialize the complaint_info dict if it doesn't exist
        if 'complaint_info' not in self.collected_info:
            self.collected_info['complaint_info'] = {}
        
        # Determine which piece of information we're collecting
        if 'customer_name' not in self.collected_info['complaint_info']:
            # Prepare user input and strip apology prefixes
            user_input = message_text.strip()
            # Handle apology prefixes: exact apology as filler, else strip prefix
            apology_prefixes = ["sorry to", "sorry for", "sorry"]
            lower_input = user_input.lower()
            for prefix in apology_prefixes:
                if lower_input == prefix:
                    return {
                        'response': "Sure! I am waiting for your name. Please let me know your name so we can proceed further.",
                        'state': self.state.name
                    }
                if lower_input.startswith(prefix + " "):
                    # Remove prefix and continue
                    user_input = user_input[len(prefix):].strip()
                    lower_input = user_input.lower()
                    break
            if user_input.lower().startswith("why"):
                prompt = (
                    "I apologize for not explaining. I ask for your full name so I can properly identify your account and address your complaint. "
                    "Could you please tell me your full name?"
                )
                return {
                    'response': prompt,
                    'state': self.state.name
                }
            # Insert filler detection for non-name responses
            filler_starters = ["let me think", "hmm", "hm", "um", "uh", "hold on", "wait", "just a sec", "just a second", "one moment"]
            for filler in filler_starters:
                if user_input.lower().startswith(filler):
                    return {
                        'response': "Sure! I am waiting for your name. Please let me know your name so we can proceed further.",
                        'state': self.state.name
                    }
            # Extract the customer's name using OpenAI for robustness
            try:
                extraction_response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract the person's full name from the following text and respond with only the name."},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.0,
                    max_tokens=20
                )
                name = extraction_response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"OpenAI name extraction failed: {e}")
                name = user_input
            self.collected_info['complaint_info']['customer_name'] = name
            # Ask for email
            prompt = f"Thank you, {name}. 🙏 So we can follow up properly, what's your email address?"
            return {
                'response': prompt,
                'state': self.state.name
            }
        
        elif 'customer_email' not in self.collected_info['complaint_info']:
            # Validate and store the email
            import re
            email = message_text.strip()
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if re.match(email_pattern, email):
                self.collected_info['complaint_info']['customer_email'] = email
                # Ask for phone number
                prompt = "Thank you for your email. 📧 What's your phone number so a representative can contact you directly?"
                return {
                    'response': prompt,
                    'state': self.state.name
                }
            else:
                # Invalid email, ask again
                prompt = "That doesn't appear to be a valid email address. 🤔 Could you please provide a valid email format? (example: name@example.com)"
                return {
                    'response': prompt,
                    'state': self.state.name
                }
        
        elif 'customer_phone' not in self.collected_info['complaint_info']:
            # Store the phone number
            self.collected_info['complaint_info']['customer_phone'] = message_text.strip()
            # Ask for complaint details
            prompt = "Thank you. 📞 Please describe your issue in detail so we can address it properly. We take all feedback seriously and will work to resolve your concerns."
            return {
                'response': prompt,
                'state': self.state.name
            }
        
        elif 'complaint_details' not in self.collected_info['complaint_info']:
            # Store the complaint details
            self.collected_info['complaint_info']['complaint_details'] = message_text
            
            # Thank the customer and confirm the complaint has been registered
            complaint_ref = f"COMP-{self.session_id}-{datetime.now().strftime('%Y%m%d')}"
            confirmation = f"✅ Thank you for bringing this to our attention. Your complaint has been registered with reference #{complaint_ref}. A representative will contact you within 24-48 hours to address your concerns. Is there anything else I can help you with today?"
            
            # Reset the state to INITIAL for potential new conversations
            self.state = ConversationState.INITIAL
            
            return {
                'response': confirmation,
                'state': self.state.name,
                'complaint_registered': True,
                'complaint_details': self.collected_info['complaint_info']
            }
        
        # Default response if somehow we got here
        return {
            'response': "I'm not sure what information you're providing. Let's start over. What's your name?",
            'state': self.state.name
        }
    
    def get_state_dict(self):
        """
        Return the current state as a dictionary for serialization
        """
        return {
            'company_id': self.company_id,
            'session_id': self.session_id,
            'state': self.state.name,
            'collected_info': self.collected_info,
            'estimated_cost': self.estimated_cost
        }
    
    @classmethod
    def from_state_dict(cls, state_dict):
        """
        Create a new MovingChatHandler from a state dictionary
        """
        handler = cls(state_dict['company_id'], state_dict['session_id'])
        handler.state = ConversationState[state_dict['state']]
        handler.collected_info = state_dict['collected_info']
        handler.estimated_cost = state_dict['estimated_cost']
        return handler
    
    def _get_email_config(self):
        """
        Get the email configuration for the company
        If no configuration exists, create a default one
        
        Returns:
            dict: Email configuration
        """
        try:
            logger.info(f"Getting email config for company_id={self.company_id}")
            
            # First try to get from database - implement proper error handling
            try:
                from core.database import db
                from models.moving_parameters import MovingParameters
                
                # Get the moving parameters for the company with proper error handling
                params = MovingParameters.query.filter_by(company_id=self.company_id).first()
                
                if params:
                    logger.info("Found moving parameters in database")
                    
                    # Check for email_config in different formats
                    if hasattr(params, 'email_config') and params.email_config:
                        logger.info("Found email_config in database parameters")
                        if isinstance(params.email_config, dict) and params.email_config.get('smtp'):
                            logger.info("Email config has SMTP configuration")
                            # Ensure all required SMTP fields exist
                            smtp = params.email_config.get('smtp', {})
                            
                            # Add default credentials if missing
                            if not smtp.get('username'):
                                smtp['username'] = "info@movergpt.com"
                                logger.info("Added default SMTP username")
                            if not smtp.get('password'):
                                smtp['password'] = "yuip pxze ammd xxym"
                                logger.info("Added default SMTP password")
                            if not smtp.get('server'):
                                smtp['server'] = "smtp.gmail.com"
                                logger.info("Added default SMTP server")
                            if not smtp.get('port'):
                                smtp['port'] = 587
                                logger.info("Added default SMTP port")
                                
                            # Ensure staff email exists
                            if not smtp.get('staff_email'):
                                smtp['staff_email'] = "staff@movergpt.com"
                                logger.info("Added default staff email")
                                
                            return params.email_config
            except Exception as db_error:
                logger.warning(f"Database error getting email config: {db_error}")
                logger.warning(f"Stack trace: {traceback.format_exc()}")
            
            # Try to get email config from another source
            try:
                from companies.models import Company
                company = Company.query.filter_by(id=self.company_id).first()
                
                if company and hasattr(company, 'settings') and company.settings:
                    logger.info("Checking company settings for email configuration")
                    settings = company.settings
                    
                    if isinstance(settings, dict) and settings.get('email_config'):
                        logger.info("Found email_config in company settings")
                        return settings.get('email_config')
            except Exception as company_error:
                logger.warning(f"Error getting company settings: {company_error}")
            
            # Use hardcoded default configuration as fallback
            logger.info("Using fallback hardcoded email configuration")
            default_config = {
                "smtp": {
                    "server": "smtp.gmail.com",
                    "port": 587,
                    "username": "info@movergpt.com",
                    "password": "squx iyum vgaw yqhv",
                    "staff_email": "staff@movergpt.com"
                },
                "staff_email_subject": "New Moving Request from {{customer_name}}",
                "customer_email_template": """Dear {{customer_name}},

Thank you for requesting a moving quote with us!

Here are the details of your request:
- From: {{origin}}
- To: {{destination}}
- Moving Date: {{move_date}}
- Move Size: {{move_size}}
- Additional Services: {{additional_services}}

Your estimated cost is ${{total_cost}}.

We will contact you shortly to confirm your booking. If you have any questions, please reply to this email or call us.

Thank you for choosing us!

Best regards,
The Moving Team
info@movergpt.com""",
                "staff_email_template": """New Moving Request

Customer Information:
- Name: {{customer_name}}
- Email: {{customer_email}}
- Phone: {{customer_phone}}

Moving Details:
- From: {{origin}}
- To: {{destination}}
- Moving Date: {{move_date}}
- Move Size: {{move_size}}
- Distance: {{distance_miles}} miles
- Additional Services: {{additional_services}}

Cost Breakdown:
- Base Rate: ${{base_rate}}
- Distance Cost: ${{distance_cost}}
- Services Cost: ${{services_cost}}
- Adjustments: ${{adjustments}}
- Total Cost: ${{total_cost}}

Booking Reference: {{booking_reference}}

Please contact the customer as soon as possible to confirm the booking."""
            }
            
            return default_config
        
        except Exception as e:
            logger.error(f"Error getting email configuration: {e}")
            logger.error(traceback.format_exc())
            return self._create_default_email_config()
    
    def _create_default_email_config(self):
        """
        Create a default email configuration
        
        Returns:
            dict: Default email configuration
        """
        return {
            "smtp": {
                "server": "smtp.gmail.com",
                "port": 587,
                "username": "info@movergpt.com",
                "password": "yuip pxze ammd xxym",
                "staff_email": "jackdev24code@gmail.com"
            },
            "staff_email_subject": "New Moving Request from {{customer_name}}",
            "customer_email_template": """Dear {{customer_name}},

Thank you for requesting a moving quote with us!

Here are the details of your request:
- From: {{origin}}
- To: {{destination}}
- Moving Date: {{move_date}}
- Move Size: {{move_size}}
- Additional Services: {{additional_services}}

Your estimated cost is ${{total_cost}}.

We will contact you shortly to confirm your booking. If you have any questions, please reply to this email or call us.

Thank you for choosing us!

Best regards,
The Moving Team
info@movergpt.com""",
            "staff_email_template": """New Moving Request

Customer Information:
- Name: {{customer_name}}
- Email: {{customer_email}}
- Phone: {{customer_phone}}

Moving Details:
- From: {{origin}}
- To: {{destination}}
- Moving Date: {{move_date}}
- Move Size: {{move_size}}
- Distance: {{distance_miles}} miles
- Additional Services: {{additional_services}}

Cost Breakdown:
- Base Rate: ${{base_rate}}
- Distance Cost: ${{distance_cost}}
- Services Cost: ${{services_cost}}
- Adjustments: ${{adjustments}}
- Total Cost: ${{total_cost}}

Booking Reference: {{booking_reference}}

Please contact the customer as soon as possible to confirm the booking."""
        } 

    def _generate_booking_summary_with_confirmation(self):
        """
        Generate a comprehensive booking summary with confirmation prompt.
        This method ensures consistent booking summary display across the application.
        
        Returns:
            dict: Response containing the booking summary with confirmation prompt
        """
        logger.info("Generating comprehensive booking summary with confirmation prompt")
        
        # Format a comprehensive summary of all collected details
        origin = self.collected_info.get('origin', 'Unknown')
        destination = self.collected_info.get('destination', 'Unknown')
        move_date = self.collected_info.get('move_date', 'Unknown')
        
        # Format the date for better display if it's in ISO format (YYYY-MM-DD)
        if move_date and move_date.count('-') == 2:
            try:
                date_obj = datetime.strptime(move_date, "%Y-%m-%d")
                move_date = date_obj.strftime("%B %d, %Y")  # Format as "June 30, 2025"
                logger.info(f"Formatted date for display: {move_date}")
            except Exception as e:
                logger.warning(f"Error formatting date: {e}")
        
        move_size = self.collected_info.get('move_size', 'Unknown')
        distance_miles = self.collected_info.get('distance_miles', 0)
        
        # Format additional services
        additional_services = self.collected_info.get('additional_services', [])
        services_text = ", ".join(additional_services) if additional_services else "None"
        
        # Format cost details with breakdown
        base_rate = self.estimated_cost.get('base_rate', 0)
        formatted_base = '{:,.2f}'.format(base_rate)
        
        distance_cost = self.estimated_cost.get('distance_cost', 0)
        formatted_distance = '{:,.2f}'.format(distance_cost)
        
        services_cost = self.estimated_cost.get('services_cost', 0)
        formatted_services = '{:,.2f}'.format(services_cost)
        
        total_cost = self.estimated_cost.get('total_cost', 0)
        formatted_total = '{:,.2f}'.format(total_cost)
        
        # Customer details
        name = self.collected_info.get('customer_name', 'Unknown')
        email = self.collected_info.get('customer_email', 'Unknown')
        phone = self.collected_info.get('customer_phone', 'Unknown')
        
        # Sanitize the phone number if it looks like a query
        if phone and any(keyword in phone.lower() for keyword in ["booking", "summary", "?"]):
            # Use a placeholder until we get a proper phone number
            phone = "Please provide your phone number"
            logger.warning(f"Phone number appears to be invalid in booking summary: {self.collected_info.get('customer_phone')}")
        
        # Generate an explicit confirmation prompt with all details
        # Make this extremely clear and prominent to ensure it displays properly
        confirmation_prompt = (
            "📋 **Booking Summary**\n"
            "\n"
            "**Moving Details:**\n"
            f"- From: {origin}\n"
            f"- To: {destination}\n"
            f"- Date: {move_date}\n"
            f"- Size: {move_size}\n"
            f"- Distance: {distance_miles} miles\n"
            f"- Additional Services: {services_text}\n"
            "\n"
            "**Customer Information:**\n"
            f"- Name: {name}\n"
            f"- Email: {email}\n"
            f"- Phone: {phone}\n"
            "\n"
            "**Cost Breakdown:**\n"
            f"- Base Rate: ${formatted_base}\n"
            f"- Distance Cost: ${formatted_distance}\n"
            f"- Additional Services: ${formatted_services}\n"
            f"- Total Estimated Cost: ${formatted_total}\n"
            "\n"
            "Is this information correct? Please confirm by replying 'yes' to book your move or 'no' to make changes."
        )
        
        logger.info(f"Generated confirmation prompt with key details: {origin} to {destination}, {move_size}, Date: {move_date}, Customer: {name}")
        
        return {
            'response': confirmation_prompt,
            'state': self.state.name
        }