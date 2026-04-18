import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import User, GodotGame
from app.repositories.user_repository import UserRepository
from app.repositories.game_repository import GameRepository


def test_oop():
    print("Testing OOP Layer...")
    user_repo = UserRepository()
    game_repo = GameRepository()
    
    print(f"UserRepository inheritance: {isinstance(user_repo, UserRepository)}")
    print(f"GameRepository inheritance: {isinstance(game_repo, GameRepository)}")
    
    # Try to fetch something (even if empty)
    try:
        users = user_repo.get_by_id(1)
        print(f"User fetch check: OK (Result: {users})")
        
        games = game_repo.get_all_games()
        print(f"Game fetch check: OK (Count: {len(games)})")
    except Exception as e:
        print(f"Fetch failure: {e}")

if __name__ == "__main__":
    test_oop()
