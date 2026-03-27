import os
import sqlite3
import json
import logging

DB_NAME = 'proglem.db'

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

        # Create Chat_Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Chat_Messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        conn.rollback()
    finally:
        conn.close()
