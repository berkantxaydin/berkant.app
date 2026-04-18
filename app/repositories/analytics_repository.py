from app.repositories.base_repository import BaseRepository
from app.models import AnalyticsLog

class AnalyticsRepository(BaseRepository):
    """
    DAL for site-wide analytics and performance tracking.
    """

    def log_request(self, method, path, ip, visitor_id, is_htmx, status_code, duration_ms):
        query = """
            INSERT INTO Analytics_Logs (method, path, ip_address, visitor_id, is_htmx, status_code, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.execute(query, (method, path, ip, visitor_id, 1 if is_htmx else 0, status_code, duration_ms), commit=True)

    def get_recent_logs(self, limit=100):
        rows = self.execute("SELECT * FROM Analytics_Logs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [AnalyticsLog.from_row(row) for row in rows]

    def clear_logs(self):
        self.execute("DELETE FROM Analytics_Logs", commit=True)
