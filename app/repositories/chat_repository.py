import sqlite3
from typing import Any, Optional, List
from app.repositories.base_repository import BaseRepository
from app.models import ChatMessage
from markupsafe import escape

class ChatRepository(BaseRepository):

    def get_rooms(self, admin_view: bool = False) -> Any:
        if admin_view:
            query = """
                SELECT r.*, j.title as jam_title
                FROM Chat_Rooms r
                LEFT JOIN Game_Jams j ON r.jam_id = j.id
                ORDER BY r.id ASC
            """
        else:
            query = "SELECT * FROM Chat_Rooms WHERE is_enabled = 1 ORDER BY id ASC"
        rows = self.execute(query)
        rooms = []
        for row in rows:
            r = dict(row)
            if 'name' in r and r['name']:
                r['name'] = r['name'].strip()
            # Ensure description exists for template safety
            if 'description' not in r or r['description'] is None:
                r['description'] = ""
            rooms.append(r)
        return rooms

    def get_room_by_id(self, room_id: int) -> Optional[sqlite3.Row]:
        return self.execute_one("SELECT * FROM Chat_Rooms WHERE id = ?", (room_id,))

    def toggle_room(self, room_id: int) -> Any:
        return self.execute("UPDATE Chat_Rooms SET is_enabled = NOT is_enabled WHERE id = ?", (room_id,), commit=True)

    def delete_room(self, room_id: int) -> Any:
        return self.execute("DELETE FROM Chat_Rooms WHERE id = ?", (room_id,), commit=True)

    def create_room(self, name: str, jam_id: Optional[int] = None) -> int:
        query = "INSERT INTO Chat_Rooms (name, jam_id, is_enabled) VALUES (?, ?, 1)"
        return self.execute(query, (name, jam_id), commit=True)

    def get_messages(self, room_id: int, limit: int = 50) -> List[ChatMessage]:
        query = """
            SELECT m.*, u.username, u.is_admin
            FROM Chat_Messages m 
            JOIN Users u ON m.user_id = u.id 
            WHERE m.room_id = ? 
            ORDER BY m.created_at DESC LIMIT ?
        """
        return [ChatMessage.from_row(row) for row in self.execute(query, (room_id, limit))]

    def add_message(self, user_id: int, room_id: int, content: str, image_url: Optional[str] = None) -> int:
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = "INSERT INTO Chat_Messages (user_id, room_id, content, image_url, created_at) VALUES (?, ?, ?, ?, ?)"
        return self.execute(query, (user_id, room_id, content, image_url, now), commit=True)

    def delete_message(self, msg_id: int, user_id: Optional[int] = None, is_admin: bool = False) -> bool:
        if is_admin:
            query = "DELETE FROM Chat_Messages WHERE id = ?"
            params = (msg_id,)
        else:
            query = "DELETE FROM Chat_Messages WHERE id = ? AND user_id = ?"
            params = (msg_id, user_id)
        
        self.execute(query, params, commit=True)
        return True
