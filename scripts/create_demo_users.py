import os
import sys

# Ensure we can import the 'app' module safely from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_db_connection
from werkzeug.security import generate_password_hash

def create_defaults():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Generate secure mathematically proven Werkzeug hashes
    admin_pw = generate_password_hash("admin123")
    user_pw = generate_password_hash("test123")
    
    try:
        cursor.execute('INSERT OR IGNORE INTO Users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                       ("admin", admin_pw, 1))
        cursor.execute('INSERT OR IGNORE INTO Users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                       ("user", user_pw, 0))
        conn.commit()
        print("Successfully injected Default User and Master Admin into SQLite!")
    except Exception as e:
        print(f"Error executing injection script: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_defaults()
