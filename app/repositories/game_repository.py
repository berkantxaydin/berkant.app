from typing import Optional, List, Any
from app.repositories.base_repository import BaseRepository
from app.models import GodotGame

class GameRepository(BaseRepository):

    def get_all_games(self) -> list[GodotGame]:
        query = """
            SELECT g.*, u.username, 
            (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes
            FROM Godot_Games g 
            JOIN Users u ON g.user_id = u.id 
            ORDER BY g.created_at DESC
        """
        return [GodotGame.from_row(row) for row in self.execute(query)]

    def get_games_by_user(self, user_id: int) -> list[GodotGame]:
        query = """
            SELECT g.*, 
            (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes
            FROM Godot_Games g 
            WHERE g.user_id = ? 
            ORDER BY g.created_at DESC
        """
        return [GodotGame.from_row(row) for row in self.execute(query, (user_id,))]

    def get_game_by_id(self, game_id: int) -> Optional[GodotGame]:
        query = """
            SELECT g.*, u.username, 
            (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes
            FROM Godot_Games g 
            JOIN Users u ON g.user_id = u.id 
            WHERE g.id = ?
        """
        return GodotGame.from_row(self.execute_one(query, (game_id,)))


    def add_game(self, user_id: int, title: str, description: str, game_url: str, jam_id: Optional[int] = None) -> int:
        query = "INSERT INTO Godot_Games (user_id, title, description, game_url, jam_id) VALUES (?, ?, ?, ?, ?)"
        return self.execute(query, (user_id, title, description, game_url, jam_id), commit=True)

    def update_game(self, game_id: int, user_id: int, title: str, description: str, is_admin: bool = False) -> bool:
        if is_admin:
            query = "UPDATE Godot_Games SET title = ?, description = ? WHERE id = ?"
            params = (title, description, game_id)
        else:
            query = "UPDATE Godot_Games SET title = ?, description = ? WHERE id = ? AND user_id = ?"
            params = (title, description, game_id, user_id)
        
        return self.execute(query, params, commit=True)

    def delete_game(self, game_id: int, user_id: int, is_admin: bool = False) -> bool:
        if is_admin:
            query = "DELETE FROM Godot_Games WHERE id = ?"
            params = (game_id,)
        else:
            query = "DELETE FROM Godot_Games WHERE id = ? AND user_id = ?"
            params = (game_id, user_id)
        
        return self.execute(query, params, commit=True)

    def increment_view(self, game_id: int) -> bool:
        query = "UPDATE Godot_Games SET views = views + 1 WHERE id = ?"
        try:
            self.execute(query, (game_id,), commit=True)
            return True
        except:
            return False

    def toggle_like(self, game_id: int, user_id: int) -> bool:
        """Toggles a like and returns True if now liked, False if unliked."""
        existing = self.execute_one("SELECT id FROM Game_Likes WHERE user_id = ? AND game_id = ?", (user_id, game_id))
        if existing:
            self.execute("DELETE FROM Game_Likes WHERE id = ?", (existing['id'],), commit=True)
            return False
        else:
            self.execute("INSERT INTO Game_Likes (user_id, game_id) VALUES (?, ?)", (user_id, game_id), commit=True)
            return True

    def get_like_count(self, game_id: int) -> int:
        row = self.execute_one("SELECT COUNT(*) as cnt FROM Game_Likes WHERE game_id = ?", (game_id,))
        return row['cnt'] if row else 0

    def is_liked_by_user(self, game_id: int, user_id: int) -> bool:
        return self.execute_one("SELECT 1 FROM Game_Likes WHERE user_id = ? AND game_id = ?", (user_id, game_id)) is not None

    def add_comment(self, game_id: int, user_id: int, content: str) -> int:
        return self.execute("INSERT INTO Game_Comments (user_id, game_id, content) VALUES (?, ?, ?)", (user_id, game_id, content), commit=True)

    def get_comments(self, game_id: int) -> List[Any]:
        query = """
            SELECT c.*, u.username 
            FROM Game_Comments c 
            JOIN Users u ON c.user_id = u.id 
            WHERE c.game_id = ? 
            ORDER BY c.created_at DESC
        """
        return self.execute(query, (game_id,))

    def delete_comment(self, comment_id: int, user_id: int, is_admin: bool = False) -> bool:
        if is_admin:
            query = "DELETE FROM Game_Comments WHERE id = ?"
            params = (comment_id,)
        else:
            query = "DELETE FROM Game_Comments WHERE id = ? AND user_id = ?"
            params = (comment_id, user_id)
        
        return self.execute(query, params, commit=True)
