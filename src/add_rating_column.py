import os
from sqlalchemy import create_engine, text

# Get the database path from the environment or use default
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'app.db')
DATABASE_URL = f'sqlite:///{db_path}'

def add_rating_column():
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Check if column exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                PRAGMA table_info(chat_messages)
            """))
            columns = [row[1] for row in result.fetchall()]
            
            if 'rating' not in columns:
                # Add the column if it doesn't exist
                conn.execute(text("""
                    ALTER TABLE chat_messages 
                    ADD COLUMN rating INTEGER
                """))
                print("Successfully added rating column to chat_messages table")
            else:
                print("Rating column already exists in chat_messages table")
            
            conn.commit()
            
    except Exception as e:
        print(f"Error adding rating column: {str(e)}")

if __name__ == "__main__":
    add_rating_column() 