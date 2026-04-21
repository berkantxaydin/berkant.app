import sqlite3
import logging
from typing import Any, Optional
from flask import has_app_context
from app.database import get_db

class BaseRepository:
    """
    Abstract Base Class for all Data Access Layer (DAL) components.
    Provides shared connection handling and transaction support.
    """
    def _get_conn(self) -> sqlite3.Connection:
        return get_db()

    def execute(self, query: str, params: tuple = (), commit: bool = False) -> Any:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if commit:
                conn.commit()
                return cursor.rowcount if "INSERT" not in query.upper() else cursor.lastrowid
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Repository Error: {e} | Query: {query}", exc_info=True)
            raise
        finally:
            # Only manually close if we are running in a background script/worker
            if not has_app_context():
                conn.close()

    def execute_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Repository Error: {e} | Query: {query}", exc_info=True)
            raise
        finally:
            if not has_app_context():
                conn.close()

    def count(self, table_name: str, condition: str = "", params: tuple = ()) -> int:
        """Helper to count rows in a table."""
        query = f"SELECT COUNT(*) FROM {table_name}"
        if condition:
            query += f" WHERE {condition}"
        row = self.execute_one(query, params)
        return row[0] if row else 0
