from app.repositories.base_repository import BaseRepository
from app.models import GameJam

class JamRepository(BaseRepository):
    """
    DAL for Game Jam events.
    """

    def get_all_jams(self) -> list[GameJam]:
        rows = self.execute("SELECT * FROM Game_Jams ORDER BY start_time DESC")
        return [GameJam.from_row(row) for row in rows]

    def get_jam_by_id(self, jam_id) -> GameJam:
        row = self.execute_one("SELECT * FROM Game_Jams WHERE id = ?", (jam_id,))
        return GameJam.from_row(row)

    def create_jam(self, title, theme, start_time, end_time, youtube_url=None):
        query = "INSERT INTO Game_Jams (title, theme, start_time, end_time, youtube_url) VALUES (?, ?, ?, ?, ?)"
        return self.execute(query, (title, theme, start_time, end_time, youtube_url), commit=True)

    def delete_jam(self, jam_id):
        self.execute("DELETE FROM Game_Jams WHERE id = ?", (jam_id,), commit=True)
