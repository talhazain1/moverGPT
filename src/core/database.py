"""
Database Module

Initializes the SQLAlchemy database with production-level connection pooling.
Configuration is loaded from environment variables.
"""

import os
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'postgresql://user:password@localhost:5432/chatbotdb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": int(os.environ.get("POOL_SIZE", 10)),
        "max_overflow": int(os.environ.get("MAX_OVERFLOW", 20)),
        "pool_timeout": int(os.environ.get("POOL_TIMEOUT", 30)),
        "pool_recycle": int(os.environ.get("POOL_RECYCLE", 1800)),
    }
    
    db.init_app(app)
    with app.app_context():
        db.create_all()
