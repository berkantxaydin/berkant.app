from typing import Any, Optional, List, Dict
from app.repositories.base_repository import BaseRepository
from app.models import AnalyticsLog

class AnalyticsRepository(BaseRepository):
    def log_request(self, method: str, path: str, visitor_id: str, is_htmx: bool, status_code: int, duration_ms: int) -> Any:
        query = """
            INSERT INTO Analytics_Logs (method, path, visitor_id, is_htmx, status_code, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        return self.execute(query, (method, path, visitor_id, 1 if is_htmx else 0, status_code, duration_ms), commit=True)

    def get_recent_logs(self, limit: int = 100) -> list[AnalyticsLog]:
        return [AnalyticsLog.from_row(row) for row in self.execute("SELECT * FROM Analytics_Logs ORDER BY created_at DESC LIMIT ?", (limit,))]

    def clear_logs(self) -> Any:
        return self.execute("DELETE FROM Analytics_Logs", commit=True)

    def get_summary_stats(self) -> Dict[str, Any]:
        """Calculates core traffic metrics."""
        query = """
            SELECT 
                COUNT(*) as total_traffic,
                COUNT(*) FILTER (WHERE is_htmx = 0 AND method = 'GET' AND path NOT LIKE '/api/%' AND path != '/health') as page_views,
                COUNT(*) FILTER (WHERE status_code >= 400) as errors,
                COUNT(DISTINCT visitor_id) as unique_devices,
                AVG(duration_ms) as avg_ms 
            FROM Analytics_Logs
        """
        row = self.execute_one(query)
        if not row:
            return {
                "total_traffic": 0, "page_views": 0, "errors": 0, 
                "unique_devices": 0, "avg_ms": 0, "error_rate": 0
            }
            
        stats = dict(row)
        total = stats['total_traffic'] or 0
        errors = stats['errors'] or 0
        stats['error_rate'] = (errors / total * 100) if total > 0 else 0
        # Ensure values are not None
        for key in ['total_traffic', 'page_views', 'errors', 'unique_devices', 'avg_ms']:
            if stats[key] is None: stats[key] = 0
            
        return stats

    def get_ai_logs(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetches recent AI lifecycle events."""
        rows = self.execute("SELECT * FROM AI_System_Logs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]
