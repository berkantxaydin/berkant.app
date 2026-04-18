import json
from app.repositories.base_repository import BaseRepository
from app.models import CVCatalog

class CVRepository(BaseRepository):
    """
    DAL for CV portfolios.
    """

    def get_all_cvs(self, search_term=None) -> list[CVCatalog]:
        if search_term:
            query = '''
                SELECT c.id, c.title, c.summary, c.cv_data, c.custom_htmx, c.user_id, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
                WHERE c.title LIKE ? OR c.cv_data LIKE ? OR u.username LIKE ?
            '''
            liketerm = f'%{search_term}%'
            rows = self.execute(query, (liketerm, liketerm, liketerm))
        else:
            query = '''
                SELECT c.id, c.title, c.summary, c.cv_data, c.custom_htmx, c.user_id, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
            '''
            rows = self.execute(query)
        
        return [CVCatalog.from_row(row) for row in rows]

    def get_cvs_by_user(self, user_id) -> list[CVCatalog]:
        query = '''
            SELECT c.id, c.title, c.summary, c.cv_data, c.custom_htmx, u.username
            FROM CV_Catalog c
            JOIN Users u ON c.user_id = u.id
            WHERE c.user_id = ?
        '''
        rows = self.execute(query, (user_id,))
        return [CVCatalog.from_row(row) for row in rows]

    def get_cv_by_id(self, cv_id) -> CVCatalog:
        query = """
            SELECT c.*, u.username, u.is_admin as author_is_admin
            FROM CV_Catalog c 
            JOIN Users u ON c.user_id = u.id 
            WHERE c.id = ?
        """
        row = self.execute_one(query, (cv_id,))
        return CVCatalog.from_row(row)


    def add_cv(self, user_id, title, summary, cv_data, custom_htmx=None):
        cv_json = json.dumps(cv_data)
        query = "INSERT INTO CV_Catalog (user_id, title, summary, cv_data, custom_htmx) VALUES (?, ?, ?, ?, ?)"
        return self.execute(query, (user_id, title, summary, cv_json, custom_htmx), commit=True)

    def update_cv(self, cv_id, user_id, title, summary, is_admin=False):
        if is_admin:
            query = "UPDATE CV_Catalog SET title = ?, summary = ? WHERE id = ?"
            params = (title, summary, cv_id)
        else:
            query = "UPDATE CV_Catalog SET title = ?, summary = ? WHERE id = ? AND user_id = ?"
            params = (title, summary, cv_id, user_id)
        
        self.execute(query, params, commit=True)
        return True

    def delete_cv(self, cv_id, user_id, is_admin=False):
        if is_admin:
            query = "DELETE FROM CV_Catalog WHERE id = ?"
            params = (cv_id,)
        else:
            query = "DELETE FROM CV_Catalog WHERE id = ? AND user_id = ?"
            params = (cv_id, user_id)
        
        self.execute(query, params, commit=True)
        return True
