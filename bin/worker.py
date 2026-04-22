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

def run_worker_loop():
    print("Background Task Worker started...")
    while True:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Grab the oldest pending/thinking task
            # We treat 'pending' and 'thinking' as ready to be processed
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
                conn = None # Set to None so finally doesn't close it again
                
                print(f"[*] Processing {task_type} task: {task_id}")
                
                try:
                    if task_type == 'ai_chat':
                        result = process_ai_task(task_id, payload)
                    elif task_type == 'game_validation':
                        result = process_game_validation(task_id, payload)
                    else:
                        result = {"status": "error", "message": f"Unknown task type: {task_type}"}
                    
                    final_status = result.get('status', 'done')
                    
                    # Write results back to DB
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
                    except Exception as inner_e:
                        print(f"[!!] Failed to record error status in DB: {inner_e}")
            else:
                conn.close()
                conn = None
                # Heartbeat every 60 seconds
                if int(time.time()) % 60 == 0:
                    print(f"[*] Worker Heartbeat: Active (Time: {time.ctime()})")
                time.sleep(1) # Wait before polling again
        except Exception as e:
            print(f"[!] Database error in worker loop: {e}")
            time.sleep(5)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

if __name__ == '__main__':
    from app.services import ai_service
    ai_service.cleanup_orphans()
    
    print("Starting background worker loop...")
    run_worker_loop()
