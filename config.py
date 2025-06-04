"""
Configuration for the Flask application.
"""

import os

class Config:
    """Base configuration class."""
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
    
    # API Keys
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
    
    # Debug mode
    DEBUG = True
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    
    # Ensure upload folders exist
    @classmethod
    def init_app(cls, app):
        """Initialize the application with this configuration."""
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        
        # Set environment variables from config if not already set
        if cls.OPENAI_API_KEY and not os.environ.get('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = cls.OPENAI_API_KEY
            
        if cls.GOOGLE_MAPS_API_KEY and not os.environ.get('GOOGLE_MAPS_API_KEY'):
            os.environ['GOOGLE_MAPS_API_KEY'] = cls.GOOGLE_MAPS_API_KEY 