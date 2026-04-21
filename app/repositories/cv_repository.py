import json
from app.repositories.base_repository import BaseRepository
from app.models import CVCatalog

class CVRepository(BaseRepository):
    """
    DAL for CV portfolios.
    """

    def get_all_cvs(self, search_term=None) -> list[CVCatalog]:
        if search_term:
            # Multi-tag search support: Split by comma and search for ANY tag
            tags = [t.strip() for t in search_term.split(',') if t.strip()]
            if not tags:
                return self.get_all_cvs()

            base_query = '''
                SELECT c.id, c.title, c.location, c.summary, c.cv_data, c.custom_htmx, c.user_id, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
            '''
            
            clauses = []
            params = []
            for tag in tags:
                liketerm = f'%{tag}%'
                clauses.append("(c.title LIKE ? OR c.cv_data LIKE ? OR u.username LIKE ? OR c.summary LIKE ? OR c.location LIKE ?)")
                params.extend([liketerm, liketerm, liketerm, liketerm, liketerm])
            
            query = f"{base_query} WHERE {' OR '.join(clauses)}"
            rows = self.execute(query, tuple(params))
        else:
            query = '''
                SELECT c.id, c.title, c.location, c.summary, c.cv_data, c.custom_htmx, c.user_id, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
            '''
            rows = self.execute(query)
        
        return [CVCatalog.from_row(row) for row in rows]

    def get_cvs_by_user(self, user_id) -> list[CVCatalog]:
        query = '''
            SELECT c.id, c.title, c.location, c.summary, c.cv_data, c.custom_htmx, u.username
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


    def add_cv(self, user_id, title, location, summary, cv_data, custom_htmx=None):
        cv_json = json.dumps(cv_data)
        query = "INSERT INTO CV_Catalog (user_id, title, location, summary, cv_data, custom_htmx) VALUES (?, ?, ?, ?, ?, ?)"
        return self.execute(query, (user_id, title, location, summary, cv_json, custom_htmx), commit=True)

    def update_cv(self, cv_id, user_id, title, location, summary, is_admin=False):
        if is_admin:
            query = "UPDATE CV_Catalog SET title = ?, location = ?, summary = ? WHERE id = ?"
            params = (title, location, summary, cv_id)
        else:
            query = "UPDATE CV_Catalog SET title = ?, location = ?, summary = ? WHERE id = ? AND user_id = ?"
            params = (title, location, summary, cv_id, user_id)
        
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
