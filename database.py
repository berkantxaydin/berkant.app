import sqlite3
import json
import logging

DB_NAME = 'proglem.db'

def get_db_connection():
    """Create a database connection to the SQLite database with strictly enforced PRAGMAs."""
    conn = sqlite3.connect(DB_NAME)
    # Allows us to access columns by name
    conn.row_factory = sqlite3.Row
    
    # Enforce strict hardware/performance constraints for SQLite
    # WAL is great for concurrency and read-heavy workloads
    conn.execute("PRAGMA journal_mode=WAL;")
    # NORMAL is recommended when using WAL mode and provides great performance
    conn.execute("PRAGMA synchronous=NORMAL;")
    
    return conn

def init_db():
    """Initialize the database schema."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                -- Additional dynamic preferences stored as JSON
                preferences JSON DEFAULT '{}'
            )
        ''')
        
        # Create CV_Catalog table
        # We store diverse CV metadata inside a JSON column to avoid schema bloat
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS CV_Catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                cv_data JSON NOT NULL, -- The main column for dynamic CV details structure
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id)
            )
        ''')
        
        conn.commit()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        conn.rollback()
    finally:
        conn.close()

def insert_example_data():
    """Insert an example user and a CV catalog entry demonstrating JSON capabilities."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Insert a user with JSON preferences
        user_prefs = json.dumps({"theme": "dark", "notifications": True})
        cursor.execute(
            "INSERT INTO Users (username, email, preferences) VALUES (?, ?, ?)",
            ("johndoe", "john@example.com", user_prefs)
        )
        user_id = cursor.lastrowid
        
        # Insert a CV with dynamic JSON data
        cv_json = json.dumps({
            "skills": ["Python", "Flask", "SQLite", "HTMX", "Pico.css"],
            "experience": [
                {"company": "TechCorp", "years": 3, "role": "Backend Engineer"},
            ],
            "certifications": {"aws": "Cloud Practitioner"}
        })
        
        cursor.execute(
            "INSERT INTO CV_Catalog (user_id, title, summary, cv_data) VALUES (?, ?, ?, ?)",
            (user_id, "Senior Python Developer", "Experienced backend dev focused on minimalism.", cv_json)
        )
        
        conn.commit()
        logging.info("Example data inserted.")
    except sqlite3.IntegrityError:
        # Ignore if John Doe already exists
        conn.rollback()
    finally:
        conn.close()

def query_example_json():
    """Example of querying inside a JSON column using SQLite JSON1 functionality."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Use json_extract/JSON operators to filter rows or extract specific properties.
        # Here we extract specific paths from 'preferences' and 'cv_data' JSON columns.
        query = '''
            SELECT 
                u.username,
                json_extract(u.preferences, '$.theme') as user_theme,
                c.title,
                json_extract(c.cv_data, '$.skills') as parsed_skills,
                json_extract(c.cv_data, '$.experience[0].role') as last_role
            FROM 
                CV_Catalog c
            JOIN 
                Users u ON c.user_id = u.id
            WHERE 
                json_extract(u.preferences, '$.theme') = 'dark'
        '''
        
        cursor.execute(query)
        results = [dict(row) for row in cursor.fetchall()]
        
        return results
    finally:
        conn.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_db()
    insert_example_data()
    print("Example Data Query Results:")
    print(json.dumps(query_example_json(), indent=2))
