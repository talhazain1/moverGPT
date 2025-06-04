import sqlite3
import os

# Define the path to the database
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'app.db')

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"Connected to database at {db_path}")

# Check if the role column exists
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

if 'role' not in column_names:
    print("Adding 'role' column to users table...")
    try:
        # Add the role column with default value 'Member'
        cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'Member';")
        conn.commit()
        print("Successfully added 'role' column to users table")
    except sqlite3.Error as e:
        print(f"Error adding column: {e}")
else:
    print("'role' column already exists in users table")

# Close the connection
conn.close()
print("Database connection closed")

print("Migration completed successfully!") 