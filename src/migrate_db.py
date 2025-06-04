#!/usr/bin/env python3
"""
Script to apply all pending Alembic/Flask-Migrate database migrations.
"""
import os

# Ensure we import main before flask_migrate so the app context is configured
from main import app
from core.database import db
from flask_migrate import Migrate, upgrade


def run_migrations():
    """Apply database migrations to the latest revision."""
    # If you use a custom DATABASE_URL, set it here or in the environment
    # os.environ['DATABASE_URL'] = 'postgresql://movergptuser:M0v3rGPT_2025!@127.0.0.1:5432/movergptdb'

    # Initialize migrate (links Alembic to our Flask app)
    migrate = Migrate(app, db)

    # Run upgrade within app context
    with app.app_context():
        print("Applying database migrations...")
        upgrade()
        print("Migrations applied successfully.")


if __name__ == '__main__':
    run_migrations() 