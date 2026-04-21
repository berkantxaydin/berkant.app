import os
import sqlite3
import logging

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_NAME = os.path.join(BASE_DIR, 'db', 'proglem.db')

def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with WAL mode and NORMAL synchronous settings."""
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

from flask import g, has_app_context

def get_db() -> sqlite3.Connection:
    """Returns a request-scoped database connection, or a fresh one if outside a request."""
    if has_app_context():
        if 'db' not in g:
            g.db = get_db_connection()
        return g.db
    else:
        # Fallback for background workers (like the one we created in Phase 1)
        return get_db_connection()

def close_db(e=None) -> None:
    """Closes the request-scoped database connection at the end of the request."""
    if has_app_context():
        db = g.pop('db', None)
        if db is not None:
            db.close()

def safe_execute(cursor: sqlite3.Cursor, sql: str, params: tuple = None) -> bool:
    """Executes SQL and suppresses errors for harmless migration checks."""
    try:
        cursor.execute(sql, params or ())
        return True
    except sqlite3.OperationalError as e:
        logging.warning(f"Database warning: {e}")
        return False
    except Exception as e:
        logging.error(f"Database error: {e}")
        return False

def ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> bool:
    """Adds a column to a table if it does not already exist."""
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        if column not in [row[1] for row in cursor.fetchall()]:
            logging.info(f"Migration: Adding column {column} to {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            return True
    except Exception as e:
        logging.error(f"Failed to ensure column {column} in {table}: {e}")
    return False

def ensure_index(cursor: sqlite3.Cursor, index_name: str, table: str, column: str) -> bool:
    """Creates an index if it does not already exist."""
    try:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
        return True
    except Exception as e:
        logging.error(f"Failed to ensure index {index_name} on {table}({column}): {e}")
    return False

def init_db() -> None:
    """Initializes the database schema with resilience and per-component commit blocks."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. CORE ANALYTICS
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
                location TEXT,
                summary TEXT,
                cv_data JSON NOT NULL,
                custom_htmx TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id)
            )
        ''')
        ensure_column(cursor, "CV_Catalog", "location", "TEXT")
        
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

        # Seed default room
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

        # 5. ASYNCHRONOUS SYSTEM TASKS (Worker Queue)
        safe_execute(cursor, '''
            CREATE TABLE IF NOT EXISTS System_Tasks (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                task_type TEXT NOT NULL,
                payload TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        ensure_index(cursor, "idx_tasks_status", "System_Tasks", "status")
        ensure_index(cursor, "idx_tasks_user", "System_Tasks", "user_id")

        conn.commit()
    except Exception as e:
        logging.error(f"Critical failure during DB init: {e}")
    finally:
        conn.close()


