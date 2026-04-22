from typing import Optional, List
import json
from app.repositories.base_repository import BaseRepository
from app.models import CVCatalog

class CVRepository(BaseRepository):

    def get_all_cvs(self, search_term: Optional[str] = None) -> list[CVCatalog]:
        if search_term:
            tags = [t.strip() for t in search_term.split(',') if t.strip()]
            if not tags:
                return self.get_all_cvs()

            base_query = '''
                SELECT c.id, c.title, c.location, c.summary, c.cv_data, c.custom_htmx, c.photo_url, c.github_url, c.user_id, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
            '''
            
            clauses, params = [], []
            for tag in tags:
                liketerm = f'%{tag}%'
                clauses.append("(c.title LIKE ? OR c.cv_data LIKE ? OR u.username LIKE ? OR c.summary LIKE ? OR c.location LIKE ?)")
                params.extend([liketerm] * 5)
            
            query = f"{base_query} WHERE {' OR '.join(clauses)}"
            rows = self.execute(query, tuple(params))
        else:
            query = '''
                SELECT c.id, c.title, c.location, c.summary, c.cv_data, c.custom_htmx, c.photo_url, c.github_url, c.user_id, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
            '''
            rows = self.execute(query)
        
        return [CVCatalog.from_row(row) for row in rows]

    def get_cvs_by_user(self, user_id: int) -> list[CVCatalog]:
        query = '''
            SELECT c.id, c.title, c.location, c.summary, c.cv_data, c.custom_htmx, c.photo_url, c.github_url, u.username
            FROM CV_Catalog c
            JOIN Users u ON c.user_id = u.id
            WHERE c.user_id = ?
        '''
        return [CVCatalog.from_row(row) for row in self.execute(query, (user_id,))]

    def get_cv_by_id(self, cv_id: int) -> Optional[CVCatalog]:
        query = """
            SELECT c.*, u.username, u.is_admin as author_is_admin
            FROM CV_Catalog c 
            JOIN Users u ON c.user_id = u.id 
            WHERE c.id = ?
        """
        return CVCatalog.from_row(self.execute_one(query, (cv_id,)))


    def add_cv(self, user_id: int, title: str, location: str, summary: str, cv_data: dict, custom_htmx: Optional[str] = None, photo_url: Optional[str] = None, github_url: Optional[str] = None) -> int:
        cv_json = json.dumps(cv_data)
        query = "INSERT INTO CV_Catalog (user_id, title, location, summary, cv_data, custom_htmx, photo_url, github_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        return self.execute(query, (user_id, title, location, summary, cv_json, custom_htmx, photo_url, github_url), commit=True)

    def update_cv(self, cv_id: int, user_id: int, title: str, location: str, summary: str, is_admin: bool = False) -> bool:
        if is_admin:
            query = "UPDATE CV_Catalog SET title = ?, location = ?, summary = ? WHERE id = ?"
            params = (title, location, summary, cv_id)
        else:
            query = "UPDATE CV_Catalog SET title = ?, location = ?, summary = ? WHERE id = ? AND user_id = ?"
            params = (title, location, summary, cv_id, user_id)
        
        return self.execute(query, params, commit=True)

    def delete_cv(self, cv_id: int, user_id: int, is_admin: bool = False) -> bool:
        if is_admin:
            query = "DELETE FROM CV_Catalog WHERE id = ?"
            params = (cv_id,)
        else:
            query = "DELETE FROM CV_Catalog WHERE id = ? AND user_id = ?"
            params = (cv_id, user_id)
        
        return self.execute(query, params, commit=True)
