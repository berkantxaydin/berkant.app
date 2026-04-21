from typing import Any, Optional, List
from app.repositories.base_repository import BaseRepository
from app.models import User

class UserRepository(BaseRepository):
    
    def get_by_username(self, username: str) -> Optional[User]:
        return User.from_row(self.execute_one("SELECT * FROM Users WHERE username = ?", (username,)))

    def get_by_email(self, email: str) -> Optional[User]:
        return User.from_row(self.execute_one("SELECT * FROM Users WHERE email = ?", (email,)))

    def get_by_id(self, user_id: int) -> Optional[User]:
        return User.from_row(self.execute_one("SELECT * FROM Users WHERE id = ?", (user_id,)))

    def create_user(self, username: str, email: str, password_hash: str, is_admin: bool = False) -> int:
        query = "INSERT INTO Users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)"
        return self.execute(query, (username, email, password_hash, 1 if is_admin else 0), commit=True)

    def update_preferences(self, user_id: int, preferences_dict: dict) -> Any:
        import json
        query = "UPDATE Users SET preferences = ? WHERE id = ?"
        return self.execute(query, (json.dumps(preferences_dict), user_id), commit=True)

    def set_admin_status(self, user_id: int, is_admin: bool) -> Any:
        query = "UPDATE Users SET is_admin = ? WHERE id = ?"
        return self.execute(query, (1 if is_admin else 0, user_id), commit=True)
