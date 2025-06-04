import os
import psycopg2
import psycopg2.extras

def update_specific_company():
    """Update Company 6 to have the correct name using raw SQL"""
    # Get database URL from environment or use default
    db_url = os.environ.get('DATABASE_URL', 'postgresql://myuser:mypassword@localhost:5432/chatbotdb')
    
    # Parse the database URL to get connection parameters
    # Format: postgresql://username:password@hostname:port/database
    if '://' in db_url:
        db_url = db_url.split('://', 1)[1]
    
    if '@' in db_url:
        auth, rest = db_url.split('@', 1)
        if ':' in auth:
            user, password = auth.split(':', 1)
        else:
            user, password = auth, ''
        
        if '/' in rest:
            host_port, dbname = rest.split('/', 1)
            if ':' in host_port:
                host, port = host_port.split(':', 1)
            else:
                host, port = host_port, '5432'
        else:
            host, port = rest, '5432'
            dbname = ''
    else:
        user, password, host, port, dbname = '', '', 'localhost', '5432', db_url
    try:
        # Connect to the database
        print(f"Connecting to database: {host}:{port}/{dbname} as {user}")
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True
        
        # Create a cursor
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Check if company exists
        cur.execute("SELECT id, name, email FROM companies WHERE id = 6")
        company = cur.fetchone()
        
        if company:
            print(f"Found company: ID={company['id']}, Name={company['name']}")
            
            # Update the company name
            cur.execute("UPDATE companies SET name = 'My Moving Journey' WHERE id = 6")
            print(f"Updated company name to: My Moving Journey")
            
            # Verify the update
            cur.execute("SELECT id, name FROM companies WHERE id = 6")
            updated_company = cur.fetchone()
            print(f"Verified company name is now: {updated_company['name']}")
        else:
            print("Company with ID 6 not found")
            
        # Close cursor and connection
        cur.close()
        conn.close()
            
    except Exception as e:
        print(f"Error updating company name: {str(e)}")

if __name__ == "__main__":
    update_specific_company()
