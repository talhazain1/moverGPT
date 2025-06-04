"""
Fix API Keys Table Script
Adds missing columns to the api_keys table
"""
from main import app
from core.database import db
from sqlalchemy import text

# SQL statements to add columns
SQL_STATEMENTS = [
    "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
    "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP",
    "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'",
    "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50)",
    "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP"
]

def apply_migrations():
    """Apply the migrations directly using SQLAlchemy."""
    with app.app_context():
        try:
            for statement in SQL_STATEMENTS:
                print(f"Executing: {statement}")
                db.session.execute(text(statement))
            
            # Commit the changes
            db.session.commit()
            print("Successfully applied all migrations!")
        except Exception as e:
            db.session.rollback()
            print(f"Error applying migrations: {e}")

if __name__ == "__main__":
    apply_migrations() 