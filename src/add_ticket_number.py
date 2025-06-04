from core.database import db
from admin_panel.models import SupportTicket
import uuid

def add_ticket_numbers():
    try:
        # Get all support tickets without a ticket number
        tickets = SupportTicket.query.filter(SupportTicket.ticket_number == None).all()
        
        for ticket in tickets:
            # Generate a unique ticket number
            ticket.ticket_number = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
        
        # Commit the changes
        db.session.commit()
        print(f"Successfully added ticket numbers to {len(tickets)} tickets")
        
    except Exception as e:
        print(f"Error adding ticket numbers: {str(e)}")
        db.session.rollback()

if __name__ == "__main__":
    add_ticket_numbers() 