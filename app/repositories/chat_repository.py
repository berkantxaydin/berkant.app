from app.repositories.base_repository import BaseRepository
from app.models import ChatMessage
from markupsafe import escape

class ChatRepository(BaseRepository):
    """
    DAL for Chat Rooms and Messages.
    """

    def get_rooms(self, admin_view=False):
        if admin_view:
            query = """
                SELECT r.*, j.title as jam_title
                FROM Chat_Rooms r
                LEFT JOIN Game_Jams j ON r.jam_id = j.id
                ORDER BY r.id ASC
            """
        else:
            query = "SELECT * FROM Chat_Rooms WHERE is_enabled = 1 ORDER BY id ASC"
        
        return self.execute(query) # Returning raw rows for internal processing or dicts

    def get_room_by_id(self, room_id):
        return self.execute_one("SELECT * FROM Chat_Rooms WHERE id = ?", (room_id,))

    def toggle_room(self, room_id):
        self.execute("UPDATE Chat_Rooms SET is_enabled = NOT is_enabled WHERE id = ?", (room_id,), commit=True)

    def delete_room(self, room_id):
        self.execute("DELETE FROM Chat_Rooms WHERE id = ?", (room_id,), commit=True)

    def create_room(self, name, jam_id=None):
        query = "INSERT INTO Chat_Rooms (name, jam_id, is_enabled) VALUES (?, ?, 1)"
        return self.execute(query, (name, jam_id), commit=True)

    def get_messages(self, room_id, limit=50) -> list[ChatMessage]:
        query = """
            SELECT m.*, u.username 
            FROM Chat_Messages m 
            JOIN Users u ON m.user_id = u.id 
            WHERE m.room_id = ? 
            ORDER BY m.created_at DESC LIMIT ?
        """
        rows = self.execute(query, (room_id, limit))
        return [ChatMessage.from_row(row) for row in rows]

    def add_message(self, user_id, room_id, content):
        query = "INSERT INTO Chat_Messages (user_id, room_id, content) VALUES (?, ?, ?)"
        return self.execute(query, (user_id, room_id, content), commit=True)

    def delete_message(self, msg_id, user_id=None, is_admin=False):
        if is_admin:
            query = "DELETE FROM Chat_Messages WHERE id = ?"
            params = (msg_id,)
        else:
            query = "DELETE FROM Chat_Messages WHERE id = ? AND user_id = ?"
            params = (msg_id, user_id)
        
        self.execute(query, params, commit=True)
        return True
