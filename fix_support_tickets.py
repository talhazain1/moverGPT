#!/usr/bin/env python3
"""
This script fixes the support_tickets table by adding the missing ticket_number column.
"""
import sys
import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment variables
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

def fix_support_tickets():
    print("Connecting to database...")
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()
    
    try:
        # Check if the ticket_number column exists
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'support_tickets' AND column_name = 'ticket_number'"))
        if result.fetchone():
            print("ticket_number column already exists. No action needed.")
            return
            
        print("Adding ticket_number column to support_tickets table...")
        
        # Start a transaction
        transaction = conn.begin()
        try:
            # Add the ticket_number column
            conn.execute(text("ALTER TABLE support_tickets ADD COLUMN ticket_number VARCHAR(20)"))
            
            # Get all existing tickets
            result = conn.execute(text("SELECT id, created_at FROM support_tickets"))
            tickets = result.fetchall()
            
            # Update each ticket with a generated ticket number
            for ticket in tickets:
                ticket_id = ticket[0]
                created_at = ticket[1] or datetime.utcnow()
                ticket_number = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
                conn.execute(
                    text("UPDATE support_tickets SET ticket_number = :ticket_number WHERE id = :id"),
                    {"ticket_number": ticket_number, "id": ticket_id}
                )
            
            # Make the column NOT NULL and add a unique constraint
            conn.execute(text("ALTER TABLE support_tickets ALTER COLUMN ticket_number SET NOT NULL"))
            conn.execute(text("ALTER TABLE support_tickets ADD CONSTRAINT uq_support_tickets_ticket_number UNIQUE (ticket_number)"))
            
            # Commit the transaction
            transaction.commit()
            print("Successfully added ticket_number column and updated existing tickets.")
            
        except Exception as e:
            transaction.rollback()
            print(f"Error during transaction: {str(e)}")
            raise
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        conn.close()
        engine.dispose()

if __name__ == "__main__":
    fix_support_tickets() 