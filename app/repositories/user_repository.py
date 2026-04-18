from app.repositories.base_repository import BaseRepository
from app.models import User

class UserRepository(BaseRepository):
    """
    DAL for User objects. Implements clean encapsulation for authentication
    and user settings logic.
    """
    
    def get_by_username(self, username: str) -> User:
        row = self.execute_one("SELECT * FROM Users WHERE username = ?", (username,))
        return User.from_row(row)

    def get_by_email(self, email: str) -> User:
        row = self.execute_one("SELECT * FROM Users WHERE email = ?", (email,))
        return User.from_row(row)

    def get_by_id(self, user_id: int) -> User:
        row = self.execute_one("SELECT * FROM Users WHERE id = ?", (user_id,))
        return User.from_row(row)

    def create_user(self, username, email, password_hash, is_admin=False) -> int:
        query = "INSERT INTO Users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)"
        return self.execute(query, (username, email, password_hash, 1 if is_admin else 0), commit=True)

    def update_preferences(self, user_id, preferences_dict):
        import json
        query = "UPDATE Users SET preferences = ? WHERE id = ?"
        return self.execute(query, (json.dumps(preferences_dict), user_id), commit=True)

    def set_admin_status(self, user_id, is_admin):
        query = "UPDATE Users SET is_admin = ? WHERE id = ?"
        return self.execute(query, (1 if is_admin else 0, user_id), commit=True)
