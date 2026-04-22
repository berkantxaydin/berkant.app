import time
import json
import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_db_connection
from app.services.ai_service import process_ai_task
from app.services.game_validator import process_game_validation

LOCK_FILE = os.path.join(os.path.dirname(__file__), '..', 'logs', 'worker.lock')

def acquire_lock():
    """Simple lock file mechanism to prevent multiple workers on Windows/Linux."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
                import psutil
                if psutil.pid_exists(old_pid):
                    print(f"Error: Another worker (PID {old_pid}) is already running.")
                    return False
        except Exception:
            pass
    
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True

def run_worker_loop():
    print("Background Task Worker started...")
    while True:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Grab the oldest pending/thinking task
            cursor.execute("""
                SELECT id, task_type, payload 
                FROM System_Tasks 
                WHERE status IN ('pending', 'thinking') 
                ORDER BY created_at ASC 
                LIMIT 1
            """)
            task = cursor.fetchone()
            
            if task:
                task_id, task_type, payload_raw = task['id'], task['task_type'], task['payload']
                payload = json.loads(payload_raw)
                
                # Claim the task
                cursor.execute("UPDATE System_Tasks SET status = 'generating', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
                conn.commit()
                conn.close()
                conn = None
                
                print(f"[*] Processing {task_type} task: {task_id}")
                
                try:
                    if task_type == 'ai_chat':
                        result = process_ai_task(task_id, payload)
                    elif task_type == 'game_validation':
                        result = process_game_validation(task_id, payload)
                    elif task_type == 'ai_translation':
                        # Translation logic integrated into worker to respect RAM limits
                        from app.services.translation_service import process_translation_batch
                        result = process_translation_batch(task_id, payload)
                    else:
                        result = {"status": "error", "message": f"Unknown task type: {task_type}"}
                    
                    final_status = result.get('status', 'done')
                    
                    conn = get_db_connection()
                    conn.execute(
                        "UPDATE System_Tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                        (final_status, json.dumps(result), task_id)
                    )
                    conn.commit()
                    print(f"[+] Task {task_id} completed with status: {final_status}")
                except Exception as e:
                    print(f"[!] Error processing task {task_id}: {e}")
                    try:
                        conn = get_db_connection()
                        conn.execute(
                            "UPDATE System_Tasks SET status = 'error', result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                            (json.dumps({"message": str(e)}), task_id)
                        )
                        conn.commit()
                    except Exception: pass
            else:
                conn.close()
                conn = None
                
                from app.services import ai_service
                ai_service.check_idle_timeout()
                
                if int(time.time()) % 60 == 0:
                    print(f"[*] Worker Heartbeat: Active (Time: {time.ctime()})")
                time.sleep(1)
        except Exception as e:
            print(f"[!] Database error in worker loop: {e}")
            time.sleep(5)
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

if __name__ == '__main__':
    from app.services import ai_service
    ai_service.cleanup_orphans()
    
    if not acquire_lock():
        sys.exit(1)
        
    try:
        run_worker_loop()
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
