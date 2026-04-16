import os
import sqlite3
import json
import logging

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_NAME = os.path.join(BASE_DIR, 'proglem.db')

def get_db_connection():
    """Create a database connection to the SQLite database with strictly enforced PRAGMAs."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    
    # Enforce strict hardware/performance constraints for SQLite
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    
    return conn

def init_db():
    """Initialize the database schema."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create Users table (IAM strict constraints)
        cursor.execute('''
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
        
        # Create CV_Catalog table
        cursor.execute('''
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
        
        # Create Game_Jams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Game_Jams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                theme TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                youtube_url TEXT
            )
        ''')

        # Create Godot_Games table (Sprint enhancements)
        # Note: jam_id added for jam submissions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Godot_Games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                jam_id INTEGER DEFAULT NULL,
                title TEXT NOT NULL,
                description TEXT,
                game_url TEXT NOT NULL,
                validation_status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (jam_id) REFERENCES Game_Jams (id) ON DELETE SET NULL
            )
        ''')

        # Game Social Features: Likes (One-time per user per game)
        cursor.execute('''
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

        # Game Social Features: Comments
        cursor.execute('''
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

        # Create Chat_Rooms table (multi-room support)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Chat_Rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                jam_id INTEGER DEFAULT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (jam_id) REFERENCES Game_Jams (id) ON DELETE SET NULL
            )
        ''')

        # Seed the default General room if it doesn't exist yet
        cursor.execute("SELECT id FROM Chat_Rooms WHERE name = '💬 General'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO Chat_Rooms (name, jam_id, is_enabled) VALUES ('💬 General', NULL, 1)")

        # Create Chat_Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Chat_Messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL DEFAULT 1,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
            )
        ''')

        # Safe migration: add room_id to pre-existing Chat_Messages tables
        try:
            cursor.execute("ALTER TABLE Chat_Messages ADD COLUMN room_id INTEGER NOT NULL DEFAULT 1")
        except Exception:
            pass  # Column already exists — no-op
        
        # Create Analytics_Logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Analytics_Logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT,
                path TEXT,
                ip_address TEXT,
                status_code INTEGER,
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        conn.rollback()
    finally:
        conn.close()
