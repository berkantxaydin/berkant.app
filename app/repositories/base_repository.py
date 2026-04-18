import sqlite3
import logging
from app.database import get_db_connection

class BaseRepository:
    """
    Abstract Base Class for all Data Access Layer (DAL) components.
    Provides shared connection handling and transaction support.
    """
    def __init__(self):
        self._db_path = None # Loaded from config if needed, usually uses get_db_connection helper

    def _get_conn(self):
        """Encapsulated method to get a raw DB connection."""
        return get_db_connection()

    def execute(self, query, params=(), commit=False):
        """Shared logic to execute simple queries without manual conn management in subclasses."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if commit:
                conn.commit()
                return cursor.lastrowid
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Repository Error: {e} | Query: {query}")
            raise
        finally:
            conn.close()

    def execute_one(self, query, params=()):
        """Shared logic to fetch a single result."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Repository Error: {e} | Query: {query}")
            raise
        finally:
            conn.close()
