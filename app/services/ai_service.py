import threading
import uuid
import os
import subprocess
import time
import urllib.request
import json
import atexit
import queue
import psutil 
import sqlite3
from datetime import datetime, timedelta
from app.database import get_db_connection

# Global paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
server_exe = os.path.join(BASE_DIR, 'bin', 'llama-server.exe')

# Configuration for the primary Gemma 4 model
AI_CONFIG = {
    "file": "gemma-4-E4B-it-Q4_K_M.gguf",
    "port": 8082,
    "context": 8192 # Expanded context for single-model setup
}


ai_processes = {}
ai_ready = False
ai_boot_thread = None

def start_llama_server():
    print(f"Starting Gemma 4 server on port {AI_CONFIG['port']}...")
    model_path = os.path.join(BASE_DIR, 'models', AI_CONFIG['file'])
    
    # Redirect errors to a log file for debugging
    log_file = os.path.join(BASE_DIR, 'llm_server_error.log')
    err_out = open(log_file, 'w', encoding='utf-8')
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    proc = subprocess.Popen( # nosec B603
        [server_exe, "-m", model_path, "--port", str(AI_CONFIG['port']), "-c", str(AI_CONFIG['context'])],
        stdout=subprocess.DEVNULL,
        stderr=err_out,
        startupinfo=startupinfo
    )
    ai_processes['chat'] = proc
    return proc

def background_initialization():
    """Background task to start Gemma server and poll health."""
    global ai_ready
    try:
        start_llama_server()
        url = f"http://127.0.0.1:{AI_CONFIG['port']}/health"
        max_retries = 90
        for _ in range(max_retries):
            try:
                # We use nosec B310 because this URL is hardcoded to localhost and safe.
                with urllib.request.urlopen(url, timeout=2) as response: # nosec B310
                    if response.status == 200:
                        ai_ready = True
                        print("DEBUG: AI Engine is ready.")
                        break
            except Exception:
                time.sleep(2)
    except Exception as e:
        print(f"CRITICAL: AI launch failed: {e}")

def initialize_ai_system():
    """Initializes the background thread for AI boot."""
    global ai_boot_thread
    ai_boot_thread = threading.Thread(target=background_initialization, daemon=True)
    ai_boot_thread.start()
    print("AI Background initialization started...")

def is_ai_ready():
    return ai_ready

# Start the background boot immediately
initialize_ai_system()

@atexit.register
def cleanup_servers():

    for name, proc in ai_processes.items():
        print(f"Terminating {name} AI server...")
        proc.terminate()

        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

ai_queue = queue.Queue()
ai_results = {}
result_timestamps = {}
active_user_tasks = {} # Tracks {user_id: task_id} for limiting concurrent requests
queue_ids = []
queue_lock = threading.Lock()

def cleanup_old_results():
    """Prevents memory leak by removing results older than 1 hour."""
    now = datetime.now()
    expired_keys = [
        tid for tid, ts in result_timestamps.items() 
        if now - ts > timedelta(minutes=15)
    ]
    for tid in expired_keys:
        ai_results.pop(tid, None)
        result_timestamps.pop(tid, None)

def get_public_snapshot():
    """Gathers enriched community metadata for AI context with social metrics."""
    snapshot = []
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row # Use Row for easier field access
        c = conn.cursor()
        
        # 1. Recent Game Jams (with schedules)
        c.execute("SELECT title, theme, start_time, end_time FROM Game_Jams ORDER BY id DESC LIMIT 3")
        jams = c.fetchall()
        if jams:
            jam_texts = []
            for j in jams:
                jam_texts.append(f"{j['title']} (Theme: {j['theme']}, Ends: {j['end_time']})")
            snapshot.append("### RECENT JAMS\n- " + "\n- ".join(jam_texts))

        # 2. Latest Games (with Social Context & Descriptions)
        # We join with Likes and Comments to give the AI a sense of 'popularity'
        c.execute("""
            SELECT g.title, g.description, 
                   (SELECT COUNT(*) FROM Game_Likes WHERE game_id = g.id) as likes,
                   (SELECT COUNT(*) FROM Game_Comments WHERE game_id = g.id) as comments
            FROM Godot_Games g 
            WHERE g.validation_status = 'Validated' 
            ORDER BY g.id DESC LIMIT 5
        """)
        games = c.fetchall()
        if games:
            game_texts = []
            for g in games:
                desc = (g['description'][:60] + "...") if g['description'] and len(g['description']) > 60 else (g['description'] or "No description")
                game_texts.append(f"'{g['title']}': {desc} [{g['likes']} likes, {g['comments']} comments]")
            snapshot.append("### FEATURED GAMES\n- " + "\n- ".join(game_texts))
            
        # 3. Public Channels
        c.execute("SELECT name FROM Chat_Rooms WHERE is_enabled = 1")
        rooms = c.fetchall()
        if rooms:
            snapshot.append("### ACTIVE CHANNELS: " + ", ".join([r['name'] for r in rooms]))

        conn.close()
    except Exception as e:
        print(f"AI Snapshot Error: {e}")
        pass
    return "\n\n".join(snapshot)

def ai_worker():
    while True:
        task = ai_queue.get()
        if task is None: break
        
        task_id, user_prompt, user_id = task
        try:
            # Platform Diagnostic Metrics
            cpu_load, ram_usage = "Unknown", "Unknown"
            total_users, total_games, active_jam = 0, 0, "None"
            
            try:
                cpu_load = psutil.cpu_percent()
                ram_info = psutil.virtual_memory()
                ram_usage = f"{ram_info.percent}% ({int(ram_info.used / (1024*1024))}MB used)"

                conn = get_db_connection()
                conn.row_factory = None
                c = conn.cursor()
                
                c.execute("SELECT COUNT(*) FROM Users")
                total_users = (c.fetchone() or [0])[0]
                
                c.execute("SELECT COUNT(*) FROM Godot_Games")
                total_games = (c.fetchone() or [0])[0]
                
                c.execute("SELECT title FROM Game_Jams WHERE end_time > datetime('now')")
                active_jam = (c.fetchone() or ["None"])[0]
                
                conn.close()
            except Exception:
                pass 
            
            # Community Knowledge Snapshot
            community_data = get_public_snapshot()

            sys_msg = (
                "You are the proglem Community Assistant. "
                "Provide brief, helpful, and community-aware answers. "
                "Do not explain your reasoning. Use following public data strictly:\n\n"
                f"--- SITE VITALS ---\n"
                f"- CPU Load: {cpu_load}%\n"
                f"- RAM Usage: {ram_usage}\n"
                f"- Developers Join: {total_users}\n"
                f"- Library Size: {total_games} games\n"
                f"- Active Jam: {active_jam}\n\n"
                f"--- COMMUNITY PULSE ---\n"
                f"{community_data}\n"
            )

            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 512,
                "temperature": 0.7,
                "stream": True
            }
            
            # Use the optimized Gemma server
            server_port = AI_CONFIG['port']
            server_url = f"http://127.0.0.1:{server_port}/v1/chat/completions"
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(server_url, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer local"})
            
            full_answer = ""
            with urllib.request.urlopen(req, timeout=300) as response: # nosec B310
                for line in response:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_chunk = line[6:]
                        if data_chunk == "[DONE]":
                            break
                        try:
                            chunk_json = json.loads(data_chunk)
                            content_piece = chunk_json['choices'][0]['delta'].get('content', '')
                            full_answer += content_piece
                            
                            with queue_lock:
                                ai_results[task_id] = {"status": "generating", "answer": full_answer}
                        except (KeyError, ValueError, TypeError):
                            pass 
            
            with queue_lock:
                ai_results[task_id] = {"status": "done", "answer": full_answer}
        except Exception as e:
            import traceback
            traceback.print_exc()
            with queue_lock:
                ai_results[task_id] = {"status": "error", "message": str(e)}
        finally:
            with queue_lock:
                if task_id in queue_ids:
                    queue_ids.remove(task_id)
                # Release user from active tracking
                for uid, tid in list(active_user_tasks.items()):
                    if tid == task_id:
                        active_user_tasks.pop(uid, None)
                        break
            ai_queue.task_done()

threading.Thread(target=ai_worker, daemon=True).start()

def submit_prompt(user_id, prompt):
    cleanup_old_results() # Purge old memory
    
    with queue_lock:
        # Check if user already has an active task
        if user_id in active_user_tasks:
            return None, False
            
        task_id = str(uuid.uuid4())
        active_user_tasks[user_id] = task_id
        queue_ids.append(task_id)
        position = len(queue_ids)
    
    ai_results[task_id] = {"status": "thinking"}
    result_timestamps[task_id] = datetime.now()
    ai_queue.put((task_id, prompt, user_id))
    
    return task_id, position > 1

def get_result(task_id):
    res = ai_results.get(task_id, {"status": "not_found"})
    if res['status'] == 'thinking':
        with queue_lock:
            try:
                res['queue_pos'] = queue_ids.index(task_id) + 1
            except ValueError:
                res['queue_pos'] = 1
    return res