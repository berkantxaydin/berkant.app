import json
import uuid
import urllib.request
from app.database import get_db_connection

def process_game_validation(task_id, payload_dict):
    """
    Core validation logic. Extracted for use by the standalone worker.
    """
    game_id = payload_dict.get('game_id')
    s3_url = payload_dict.get('url')
    
    print(f"[{task_id}] Validating game {game_id}...")
    
    success = False
    try:
        # We do a lightweight HTTP HEAD request to verify file existence without downloading it
        if s3_url.startswith("http://") or s3_url.startswith("https://"):
            req = urllib.request.Request(s3_url, method='HEAD')
            try:
                with urllib.request.urlopen(req, timeout=5) as response: # nosec B310
                    if response.status in [200, 301, 302, 204]:
                        success = True
            except Exception as e:
                print(f"[{task_id}] Network validation failed: {e}")
        else:
            # Local fallback: Rule enforcement for strictly ends with .zip or satisfies WebGL markers
            cloudflare_r2_patterns = [".zip", "/play_mock/", "r2.cloudflarestorage.com", "cloudflared.com", "/submissions/"]
            if any(pattern in s3_url.lower() for pattern in cloudflare_r2_patterns):
                success = True
    except Exception as e:
        print(f"[{task_id}] Worker Failure: {e}")
    
    # Update our SQLite Database status using Native Repository logic
    status_flag = "Approved" if success else "Rejected"
    print(f"[{task_id}] Validation Complete! Outcome: {status_flag}")
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Godot_Games SET validation_status = ? WHERE id = ?", (status_flag, game_id))
        conn.commit()
    except Exception as e:
        print(f"[{task_id}] SQLite Flagging Error: {e}")
    finally:
        conn.close()
    
    return {"status": "done", "validation_status": status_flag}

# Note: validation_worker thread and local queue removed.
# This logic is now handled in bin/worker.py

def submit_validation_job(game_id, url):
    """Generates an internal database-backed task."""
    task_id = str(uuid.uuid4())
    payload = json.dumps({"game_id": game_id, "url": url})
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO System_Tasks (id, task_type, payload, status) VALUES (?, 'game_validation', ?, 'pending')",
            (task_id, payload)
        )
        conn.commit()
        return task_id
    finally:
        conn.close()
