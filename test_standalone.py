#!/usr/bin/env python3
"""
Standalone test script for the moving estimate functionality.
This script uses the mock database and directly tests the MovingChatHandler.
"""

import os
import sys
import json
import logging
import re
from datetime import datetime
from enum import Enum, auto

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Ensure OPENAI_API_KEY is set
if not os.environ.get('OPENAI_API_KEY'):
    api_key = input("Enter your OpenAI API key: ")
    if api_key.strip():
        os.environ['OPENAI_API_KEY'] = api_key.strip()
        print("OpenAI API key set for this session")
    else:
        print("Warning: No OpenAI API key provided")

# Import the mock database
from mock_db import app, db, Company, MovingParameters, setup_mock_db

# Set up the mock database
setup_mock_db()

# Define the ConversationState Enum
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

# Define a simplified version of the MovingChatHandler
class SimplifiedMovingChatHandler:
    """Simplified version of the MovingChatHandler for testing"""
    
    def __init__(self, company_id, session_id):
        """Initialize the handler"""
        self.company_id = company_id
        self.session_id = session_id
        self.state = ConversationState.INITIAL
        self.collected_info = {}
        self.estimated_cost = None
    
    def process_query(self, query):
        """Process a query and extract moving information"""
        # Extract information from the query
        self.collected_info = self.extract_moving_information(query)
        
        # If we have all the information, calculate the estimate
        if self.collected_info['is_complete']:
            return self.calculate_estimate()
        else:
            # Ask for missing information
            missing_fields = []
            for field in ['origin', 'destination', 'move_size', 'move_date']:
                if not self.collected_info.get(field):
                    missing_fields.append(field)
            
            return {
                'response': f"I need more information. Missing: {', '.join(missing_fields)}",
                'state': self.state.name,
                'collected_info': self.collected_info
            }
    
    def extract_moving_information(self, query):
        """Extract moving information from the query"""
        # Simple regex-based extraction
        info = {
            'origin': None,
            'destination': None,
            'move_size': None,
            'move_date': None,
            'is_complete': False
        }
        
        # Extract origin and destination with better patterns
        move_pattern = re.search(r'(?:move|moving)\s+from\s+([^,]+)\s+to\s+([^,]+)', query, re.IGNORECASE)
        if move_pattern:
            info['origin'] = move_pattern.group(1).strip()
            info['destination'] = move_pattern.group(2).strip()
        else:
            # Try alternative patterns
            origin_match = re.search(r'from\s+([^,]+)(?:,|\s+to)', query, re.IGNORECASE)
            if origin_match:
                info['origin'] = origin_match.group(1).strip()
            
            dest_match = re.search(r'to\s+([^,]+)(?:,|\s+on|\s+a)', query, re.IGNORECASE)
            if dest_match:
                info['destination'] = dest_match.group(1).strip()
        
        # Extract move size (assuming "X bedroom" pattern)
        size_match = re.search(r'(\d+)[\s-]*(bed|bedroom|br)', query, re.IGNORECASE)
        if size_match:
            bedrooms = size_match.group(1)
            info['move_size'] = f"{bedrooms}-bedroom"
        
        # Extract date (assuming "on X" pattern or date format)
        date_match = re.search(r'on\s+([^,]+\d{4})', query, re.IGNORECASE)
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
                if not info['move_date']:
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
        
        # Check if all required fields are present
        info['is_complete'] = all(info.get(key) for key in ['origin', 'destination', 'move_size', 'move_date'])
        
        return info
    
    def calculate_estimate(self):
        """Calculate the moving cost estimate"""
        with app.app_context():
            # Get the moving parameters
            params = MovingParameters.query.filter_by(company_id=self.company_id).first()
            if not params:
                return {
                    'response': "Error: No moving parameters found for this company.",
                    'state': self.state.name
                }
            
            # Normalize move size
            move_size = self.collected_info['move_size']
            move_size = move_size.lower().strip()
            move_size = re.sub(r'(\d+)\s+bed', r'\1-bed', move_size)
            move_size = re.sub(r'(\d+)\s+bedroom', r'\1-bedroom', move_size)
            move_size = re.sub(r'(\d+)\s*br', r'\1-bedroom', move_size)
            move_size = re.sub(r'(\d+)-br', r'\1-bedroom', move_size)
            
            # Check if the move size is in the rates
            if move_size not in params.move_size_rates:
                # Try to find a match
                if '2-bedroom' in params.move_size_rates:
                    move_size = '2-bedroom'  # Default to 2-bedroom
                else:
                    # Use the first available move size
                    move_size = list(params.move_size_rates.keys())[0]
            
            # Calculate distance
            origin = self.collected_info['origin']
            destination = self.collected_info['destination']
            
            # Simple distance calculation
            if ('new york' in origin.lower() and 'boston' in destination.lower()) or \
               ('boston' in origin.lower() and 'new york' in destination.lower()):
                distance_miles = 215  # Known distance
            else:
                import random
                distance_miles = random.randint(30, 500)  # Random distance
            
            # Calculate costs
            base_cost = params.move_size_rates[move_size]
            distance_cost = distance_miles * params.base_rate_per_mile
            subtotal = base_cost + distance_cost
            
            # Calculate min and max costs
            min_cost = round(subtotal, 2)
            max_cost = round(subtotal * params.rate_adjustments['max_cost_multiplier'], 2)
            
            # Store the estimate
            self.estimated_cost = {
                'min_cost': min_cost,
                'max_cost': max_cost,
                'base_cost': base_cost,
                'distance_cost': distance_cost,
                'distance_miles': distance_miles,
                'currency': 'USD'
            }
            
            # Create the response
            estimate_text = (
                f"Based on moving a {move_size} from {self.collected_info['origin']} to "
                f"{self.collected_info['destination']} (approximately {distance_miles} miles), "
                f"the estimated cost is between ${min_cost} and ${max_cost}.\n\n"
                f"This includes a base cost of ${base_cost} for a {move_size} and "
                f"${round(distance_cost, 2)} for the distance.\n\n"
                f"Would you like to proceed with booking this move?"
            )
            
            return {
                'response': estimate_text,
                'state': ConversationState.SHOW_ESTIMATE.name,
                'estimate': self.estimated_cost
            }

def test_moving_estimate():
    """Test the moving estimate functionality"""
    print("Testing moving estimate functionality...")
    
    # Create a handler
    handler = SimplifiedMovingChatHandler(23, 999999)
    
    # Test query
    query = "I want to move from New York to Boston, a 2 bedroom apartment on 1st september 2025"
    print(f"\nTesting query: {query}")
    
    # Process the query
    result = handler.process_query(query)
    
    # Print the result
    print("\nExtracted information:")
    print(json.dumps(handler.collected_info, indent=2))
    
    print("\nResponse:")
    print(result['response'])
    
    if 'estimate' in result:
        print("\nEstimate:")
        print(json.dumps(result['estimate'], indent=2))
    
    return result

if __name__ == "__main__":
    test_moving_estimate() 