from app.database import get_db_connection

class GameRepository:
    @staticmethod
    def get_all_games():
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT g.*, u.username FROM Godot_Games g JOIN Users u ON g.user_id = u.id ORDER BY g.created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_games_by_user(user_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Godot_Games WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
            
    @staticmethod
    def get_game_by_id(game_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Godot_Games WHERE id = ?", (game_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def add_game(user_id, title, description, game_url, jam_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Godot_Games (user_id, title, description, game_url, jam_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, title, description, game_url, jam_id)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def update_game(game_id, user_id, title, description, is_admin=False):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if is_admin:
                cursor.execute("UPDATE Godot_Games SET title = ?, description = ? WHERE id = ?", (title, description, game_id))
            else:
                cursor.execute("UPDATE Godot_Games SET title = ?, description = ? WHERE id = ? AND user_id = ?", (title, description, game_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def delete_game(game_id, user_id, is_admin=False):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if is_admin:
                cursor.execute("DELETE FROM Godot_Games WHERE id = ?", (game_id,))
            else:
                cursor.execute("DELETE FROM Godot_Games WHERE id = ? AND user_id = ?", (game_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
