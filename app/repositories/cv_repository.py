import json
from app.database import get_db_connection

class CVRepository:
    @staticmethod
    def get_all_cvs(search_term=None, city=None, department=None, skill=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            base_query = '''
                SELECT c.id, c.title, c.summary, c.cv_data, c.custom_htmx, c.user_id, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
            '''
            conditions = []
            params = []

            if search_term:
                liketerm = f'%{search_term}%'
                conditions.append('(c.title LIKE ? OR c.summary LIKE ? OR c.cv_data LIKE ? OR u.username LIKE ?)')
                params.extend([liketerm, liketerm, liketerm, liketerm])

            if conditions:
                base_query += ' WHERE ' + ' AND '.join(conditions)

            cursor.execute(base_query, params)

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict['cv_data'] = json.loads(row_dict['cv_data'])
                cv_data = row_dict['cv_data']

                # Şehir filtresi
                if city:
                    cv_city = cv_data.get('city', '')
                    if city.lower() not in cv_city.lower():
                        continue

                # Departman filtresi
                if department:
                    cv_dept = cv_data.get('department', '')
                    if department.lower() not in cv_dept.lower():
                        continue

                # Yetkinlik filtresi
                if skill:
                    cv_skills = [s.lower() for s in cv_data.get('skills', [])]
                    if skill.lower() not in cv_skills:
                        continue

                results.append(row_dict)
            return results
        finally:
            conn.close()

    @staticmethod
    def get_cvs_by_user(user_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            query = '''
                SELECT c.id, c.title, c.summary, c.cv_data, c.custom_htmx, u.username
                FROM CV_Catalog c
                JOIN Users u ON c.user_id = u.id
                WHERE c.user_id = ?
            '''
            cursor.execute(query, (user_id,))
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict['cv_data'] = json.loads(row_dict['cv_data'])
                results.append(row_dict)
            return results
        finally:
            conn.close()

    @staticmethod
    def get_cv_by_id(cv_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM CV_Catalog WHERE id = ?", (cv_id,))
            row = cursor.fetchone()
            if not row: return None
            row_dict = dict(row)
            row_dict['cv_data'] = json.loads(row_dict['cv_data'])
            return row_dict
        finally:
            conn.close()

    @staticmethod
    def add_cv(user_id, title, summary, cv_data, custom_htmx=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cv_json = json.dumps(cv_data)
            cursor.execute(
                "INSERT INTO CV_Catalog (user_id, title, summary, cv_data, custom_htmx) VALUES (?, ?, ?, ?, ?)",
                (user_id, title, summary, cv_json, custom_htmx)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def update_cv(cv_id, user_id, title, summary, is_admin=False):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if is_admin:
                cursor.execute("UPDATE CV_Catalog SET title = ?, summary = ? WHERE id = ?", (title, summary, cv_id))
            else:
                cursor.execute("UPDATE CV_Catalog SET title = ?, summary = ? WHERE id = ? AND user_id = ?", (title, summary, cv_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def delete_cv(cv_id, user_id, is_admin=False):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if is_admin:
                cursor.execute("DELETE FROM CV_Catalog WHERE id = ?", (cv_id,))
            else:
                cursor.execute("DELETE FROM CV_Catalog WHERE id = ? AND user_id = ?", (cv_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
