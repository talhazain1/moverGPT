#!/usr/bin/env python3
"""
Mock database module for testing the moving estimate functionality.
This creates a simple in-memory database with the necessary tables and data.
"""

import os
import sys
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Define models
class Company(db.Model):
    """Company model."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    niche = db.Column(db.String(100))
    
class MovingParameters(db.Model):
    """Moving parameters model."""
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    move_size_rates = db.Column(db.JSON, default={})
    base_rate_per_mile = db.Column(db.Float, default=2.0)
    additional_service_costs = db.Column(db.JSON, default={})
    rate_adjustments = db.Column(db.JSON, default={})

class ChatbotConfig(db.Model):
    """Chatbot configuration model."""
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    bot_name = db.Column(db.String(100), default="MovingBot")
    purpose = db.Column(db.String(500))
    goal = db.Column(db.String(500))
    role = db.Column(db.String(100))
    trained_model = db.Column(db.LargeBinary)
    configuration = db.Column(db.JSON, default={})
    knowledge_base = db.Column(db.JSON, default={})
    last_trained_at = db.Column(db.DateTime)

def setup_mock_db():
    """Set up the mock database with test data."""
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create a test company
        company = Company(id=23, name="Test Moving Company", niche="moving")
        db.session.add(company)
        
        # Create moving parameters
        params = MovingParameters(
            company_id=23,
            move_size_rates={
                "studio": 500,
                "1-bedroom": 700,
                "2-bedroom": 900,
                "3-bedroom": 1200,
                "4-bedroom": 1500
            },
            base_rate_per_mile=2.5,
            additional_service_costs={
                "packing": {
                    "studio": 200,
                    "1-bedroom": 300,
                    "2-bedroom": 400,
                    "3-bedroom": 500,
                    "4-bedroom": 600
                },
                "storage": {
                    "studio": 100,
                    "1-bedroom": 150,
                    "2-bedroom": 200,
                    "3-bedroom": 250,
                    "4-bedroom": 300
                }
            },
            rate_adjustments={
                "rural_location_rate": 0.1,
                "seasonality_rate": 0.15,
                "max_cost_multiplier": 1.2
            }
        )
        db.session.add(params)
        
        # Create chatbot config
        chatbot = ChatbotConfig(
            company_id=23,
            bot_name="MovingBot",
            purpose="Help customers with moving estimates",
            goal="Provide accurate moving cost estimates",
            role="assistant"
        )
        db.session.add(chatbot)
        
        # Commit the changes
        db.session.commit()
        
        logger.info("Mock database set up successfully")
        
        # Verify the data
        company = Company.query.get(23)
        logger.info(f"Company: {company.name}, niche: {company.niche}")
        
        params = MovingParameters.query.filter_by(company_id=23).first()
        logger.info(f"MovingParameters: {json.dumps(params.move_size_rates, indent=2)}")
        
        return True

if __name__ == "__main__":
    setup_mock_db()
    print("Mock database set up successfully. You can now test the moving estimate functionality.") 