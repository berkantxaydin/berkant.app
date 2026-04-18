import os
import sqlite3
import logging

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_NAME = os.path.join(BASE_DIR, 'db', 'proglem.db')

def get_db_connection():
    """Create a database connection to the SQLite database with strictly enforced PRAGMAs."""
    # Ensure the directory for the database exists (required for CI/CD environments)
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    
    # Enforce strict hardware/performance constraints for SQLite
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    
    return conn

def safe_execute(cursor, sql, params=None):
    """Executes a SQL statement and catches common SQLite errors without rolling back the entire transaction context."""
    try:
        cursor.execute(sql, params or ())
        return True
    except sqlite3.OperationalError as e:
        # We specifically log these as warnings because they often occur during harmless migration checks
        logging.warning(f"Database operation warning (safe to ignore if already exists): {e}")
        return False
    except Exception as e:
        logging.error(f"Database operation failure: {e}")
        return False

def ensure_column(cursor, table, column, definition):
    """Add a column to a table only if it does not already exist."""
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            logging.info(f"Migration: Adding column {column} to {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            return True
    except Exception as e:
        logging.error(f"Failed to ensure column {column} in {table}: {e}")
    return False

def ensure_index(cursor, index_name, table, column):
    """Create an index only if it does not already exist."""
    try:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
        return True
    except Exception as e:
        logging.error(f"Failed to ensure index {index_name} on {table}({column}): {e}")
    return False

def init_db():
    """Initialize the database schema with high resilience and per-component commit blocks."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. CORE ANALYTICS (Highest Priority)
        # We ensure this table first because the layout depends on it immediately
        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Analytics_Logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT,
                path TEXT,
                ip_address TEXT,
                visitor_id TEXT,
                is_htmx BOOLEAN DEFAULT 0,
                status_code INTEGER,
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        ensure_column(cursor, "Analytics_Logs", "visitor_id", "TEXT")
        ensure_column(cursor, "Analytics_Logs", "is_htmx", "BOOLEAN DEFAULT 0")
        ensure_index(cursor, "idx_analytics_path", "Analytics_Logs", "path")
        ensure_index(cursor, "idx_analytics_created", "Analytics_Logs", "created_at")

        # 2. SYSTEM & USER MANAGEMENT
        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS AI_System_Logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT, 
                status TEXT,     
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                preferences JSON DEFAULT '{}'
            )
        ''')

        # 3. CONTENT & SOCIAL TABLES
        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS CV_Catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                cv_data JSON NOT NULL,
                custom_htmx TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id)
            )
        ''')
        
        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Game_Jams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                theme TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                youtube_url TEXT
            )
        ''')

        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Godot_Games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                jam_id INTEGER DEFAULT NULL,
                title TEXT NOT NULL,
                description TEXT,
                game_url TEXT NOT NULL,
                validation_status TEXT DEFAULT 'Pending',
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (jam_id) REFERENCES Game_Jams (id) ON DELETE SET NULL
            )
        ''')

        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Game_Likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES Godot_Games(id) ON DELETE CASCADE,
                UNIQUE(user_id, game_id)
            )
        ''')

        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Game_Comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES Godot_Games(id) ON DELETE CASCADE
            )
        ''')

        # 4. CHAT SYSTEM
        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Chat_Rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                jam_id INTEGER DEFAULT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (jam_id) REFERENCES Game_Jams (id) ON DELETE SET NULL
            )
        ''')

        # Seed default room if missing
        try:
            cursor.execute("SELECT id FROM Chat_Rooms WHERE name = '💬 General'")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO Chat_Rooms (name, jam_id, is_enabled) VALUES ('💬 General', NULL, 1)")
        except Exception:
            pass

        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS Chat_Messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL DEFAULT 1,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
            )
        ''')
        ensure_column(cursor, "Chat_Messages", "room_id", "INTEGER NOT NULL DEFAULT 1")

        conn.commit()
        logging.info("Database schema verified/initialized successfully.")
    except Exception as e:
        logging.error(f"Critical failure during database initialization: {e}")
    finally:
        conn.close()


