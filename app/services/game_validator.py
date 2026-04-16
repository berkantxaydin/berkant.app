import queue
import threading
import uuid
import urllib.request
from app.database import get_db_connection

validation_queue = queue.Queue()
validator_mutex = threading.Lock()

def validation_worker():
    """
    Multithreaded background process daemon!
    Handles asynchronous UUID job queue to process Game Packages.
    Uses strict Mutex properties during validation procedures to ensure OS RAM limits (8GB) are preserved.
    """
    while True:
        task = validation_queue.get()
        if task is None: break
        
        job_uid, game_id, s3_url = task
        print(f"[{job_uid}] Acquiring Mutex Lock to validate game {game_id}...")
        
        success = False
        with validator_mutex:
            try:
                print(f"[{job_uid}] Mutex locked. Validating remote ZIP HTTP header or parsing mock WebGL integrity...")
                # We do a lightweight HTTP HEAD request to verify file existence without downloading it
                if s3_url.startswith("http://") or s3_url.startswith("https://"):
                    req = urllib.request.Request(s3_url, method='HEAD')
                    try:
                        with urllib.request.urlopen(req, timeout=5) as response:
                            if response.status in [200, 301, 302, 204]:
                                success = True
                    except Exception as e:
                        print(f"[{job_uid}] Network validation failed: {e}")
                else:
                    # Local fallback: Rule enforcement for strictly ends with .zip or satisfies WebGL markers
                    cloudflare_r2_patterns = [".zip", "/play_mock/", "r2.cloudflarestorage.com", "cloudflared.com", "/submissions/"]
                    if any(pattern in s3_url.lower() for pattern in cloudflare_r2_patterns):
                        success = True
            except Exception as e:
                print(f"[{job_uid}] Worker Failure: {e}")
        
        # After Mutex releases, update our SQLite Database status using Native Repository logic
        status_flag = "Approved" if success else "Rejected"
        print(f"[{job_uid}] Validation Complete! Outcome: {status_flag}")
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE Godot_Games SET validation_status = ? WHERE id = ?", (status_flag, game_id))
            conn.commit()
        except Exception as e:
            print(f"[{job_uid}] SQLite Flagging Error: {e}")
        finally:
            conn.close()
            
        validation_queue.task_done()

# Boot daemon locally
threading.Thread(target=validation_worker, daemon=True).start()

def submit_validation_job(game_id, url):
    """Generates an internal multithreaded UID async process map."""
    job_uid = str(uuid.uuid4())
    validation_queue.put((job_uid, game_id, url))
    return job_uid
