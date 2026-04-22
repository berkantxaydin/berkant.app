from typing import Any, Optional, List, Dict
from app.repositories.base_repository import BaseRepository
from app.models import GameJam

class JamRepository(BaseRepository):

    def get_all_jams(self) -> list[GameJam]:
        return [GameJam.from_row(row) for row in self.execute("SELECT * FROM Game_Jams ORDER BY start_time DESC")]

    def get_jam_by_id(self, jam_id: int) -> Optional[GameJam]:
        return GameJam.from_row(self.execute_one("SELECT * FROM Game_Jams WHERE id = ?", (jam_id,)))

    def create_jam(self, title: str, theme: str, start_time: str, end_time: str, youtube_url: Optional[str] = None, image_url: Optional[str] = None) -> int:
        """Creates a jam and a linked chat room."""
        # Note: We use raw connection here to ensure atomicity for dual insert
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Game_Jams (title, theme, start_time, end_time, youtube_url, image_url) VALUES (?, ?, ?, ?, ?, ?)",
                (title, theme, start_time, end_time, youtube_url, image_url)
            )
            jam_id = cursor.lastrowid
            # Auto-create a linked chat room for this jam
            cursor.execute(
                "INSERT INTO Chat_Rooms (name, jam_id, is_enabled) VALUES (?, ?, 1)",
                (f"🎮 {title}", jam_id)
            )
            conn.commit()
            return jam_id
        except Exception:
            conn.rollback()
            raise
        finally:
            pass

    def update_jam(self, jam_id: int, title: str, theme: str, start_time: str, end_time: str, youtube_url: Optional[str] = None, image_url: Optional[str] = None) -> bool:
        query = """
            UPDATE Game_Jams 
            SET title = ?, theme = ?, start_time = ?, end_time = ?, youtube_url = ?, image_url = ? 
            WHERE id = ?
        """
        self.execute(query, (title, theme, start_time, end_time, youtube_url, image_url, jam_id), commit=True)
        return True

    def delete_jam(self, jam_id: int) -> Any:
        return self.execute("DELETE FROM Game_Jams WHERE id = ?", (jam_id,), commit=True)

    def get_jams_with_games(self) -> List[Dict[str, Any]]:
        """Fetches all jams and their games using only 2 queries to prevent N+1 bottleneck."""
        import datetime
        # 1. Fetch all jams
        jams_raw = self.execute("SELECT * FROM Game_Jams ORDER BY start_time DESC")
        jams_dict = {row['id']: dict(row) for row in jams_raw}
        
        now = datetime.datetime.now()
        
        for j in jams_dict.values():
            j['games'] = []
            
            # Calculate Status
            # SQLite stores dates as strings, let's parse them
            try:
                start = datetime.datetime.fromisoformat(j['start_time'].replace(' ', 'T'))
                end = datetime.datetime.fromisoformat(j['end_time'].replace(' ', 'T'))
                
                if now < start:
                    j['status'] = 'not_started'
                elif now <= end:
                    j['status'] = 'ongoing'
                else:
                    j['status'] = 'ended'
            except:
                j['status'] = 'ongoing' # Fallback

        # 2. Fetch ALL games belonging to ANY of these jams in a single query
        games_query = """
            SELECT g.*, u.username, 
            (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes
            FROM Godot_Games g 
            JOIN Users u ON g.user_id = u.id 
            WHERE g.jam_id IS NOT NULL
            ORDER BY g.created_at DESC
        """
        all_games = self.execute(games_query)
        
        # 3. Map the games to their respective jams in memory
        for game_row in all_games:
            game = dict(game_row)
            jam_id = game['jam_id']
            if jam_id in jams_dict:
                jams_dict[jam_id]['games'].append(game)
                
        return list(jams_dict.values())
