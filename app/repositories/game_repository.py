from app.repositories.base_repository import BaseRepository
from app.models import GodotGame

class GameRepository(BaseRepository):
    """
    DAL for Godot Game submissions.
    """

    def get_all_games(self) -> list[GodotGame]:
        query = """
            SELECT g.*, u.username, 
            (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes
            FROM Godot_Games g 
            JOIN Users u ON g.user_id = u.id 
            ORDER BY g.created_at DESC
        """
        rows = self.execute(query)
        return [GodotGame.from_row(row) for row in rows]

    def get_games_by_user(self, user_id) -> list[GodotGame]:
        query = """
            SELECT g.*, 
            (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes
            FROM Godot_Games g 
            WHERE g.user_id = ? 
            ORDER BY g.created_at DESC
        """
        rows = self.execute(query, (user_id,))
        return [GodotGame.from_row(row) for row in rows]

    def get_game_by_id(self, game_id) -> GodotGame:
        query = """
            SELECT g.*, u.username, 
            (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes
            FROM Godot_Games g 
            JOIN Users u ON g.user_id = u.id 
            WHERE g.id = ?
        """
        row = self.execute_one(query, (game_id,))
        return GodotGame.from_row(row)


    def add_game(self, user_id, title, description, game_url, jam_id=None):
        query = "INSERT INTO Godot_Games (user_id, title, description, game_url, jam_id) VALUES (?, ?, ?, ?, ?)"
        return self.execute(query, (user_id, title, description, game_url, jam_id), commit=True)

    def update_game(self, game_id, user_id, title, description, is_admin=False):
        if is_admin:
            query = "UPDATE Godot_Games SET title = ?, description = ? WHERE id = ?"
            params = (title, description, game_id)
        else:
            query = "UPDATE Godot_Games SET title = ?, description = ? WHERE id = ? AND user_id = ?"
            params = (title, description, game_id, user_id)
        
        self.execute(query, params, commit=True)
        return True # Simplified for now

    def delete_game(self, game_id, user_id, is_admin=False):
        if is_admin:
            query = "DELETE FROM Godot_Games WHERE id = ?"
            params = (game_id,)
        else:
            query = "DELETE FROM Godot_Games WHERE id = ? AND user_id = ?"
            params = (game_id, user_id)
        
        self.execute(query, params, commit=True)
        return True

    def increment_view(self, game_id):
        query = "UPDATE Godot_Games SET views = views + 1 WHERE id = ?"
        try:
            self.execute(query, (game_id,), commit=True)
            return True
        except:
            return False
