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
import logging
import socket
from app.database import get_db_connection

# App-wide logger for integrated logging
logger = logging.getLogger('flask.app')

# Global paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# In Docker/Linux, we use the installed package command. 
# On Windows, we try to use the local binary if available.
if os.name == 'nt':
    server_exe = os.path.join(BASE_DIR, 'bin', 'llama-server.exe')
else:
    # On Linux/Docker, llama-cpp-python[server] provides the command
    server_exe = "python3" # We will use -m llama_cpp.server

# Configuration for the primary Qwen 2.5 7B model
AI_CONFIG = {
    "file": "qwen2.5-7b-instruct-q3_k_m.gguf",
    "port": 8082,
    "context": 4096
}


ai_processes = {}
ai_ready = False
ai_boot_thread = None
ai_booting = False
ai_init_lock = threading.Lock() # Robustness: prevent multiple boot threads
PID_FILE = os.path.join(BASE_DIR, 'logs', '.ai_pid')
LAST_RESTART_TIME = 0.0
RESTART_COOLDOWN = 10 # 10 seconds debounce to prevent rapid-fire spawn loops

# Configuration for RAM conservation (unloading after inactivity)
IDLE_TIMEOUT = 7 * 60  # 7 minutes
last_activity_time = time.time()

def log_ai_event(event_type, status, message):
    """Logs an AI event to both the standard logger and the database."""
    # 1. Standard Logger
    log_msg = f"[AI {event_type}] ({status}) {message}"
    if status == 'ERROR':
        logger.error(log_msg)
    elif status == 'WARNING':
        logger.warning(log_msg)
    else:
        logger.info(log_msg)

    # 2. Database Logger
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO AI_System_Logs (event_type, status, message, created_at) VALUES (?, ?, ?, datetime('now', 'localtime'))",
            (event_type, status, message)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log AI event to DB: {e}")

def is_port_in_use(port):
    """Checks if a local TCP port is currently occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def cleanup_orphans():
    """Forcefully kills any orphaned llama-server processes to free GPU/RAM."""
    target_names = ["llama-server.exe", "llama-server"]
    
    # 1. First, try cleaning using the persistent PID file if it exists
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
                if psutil.pid_exists(old_pid):
                    p = psutil.Process(old_pid)
                    if any(tn in p.name().lower() for tn in target_names):
                        print(f"Cleaning up persistent AI PID: {old_pid}")
                        for child in p.children(recursive=True):
                            child.kill()
                        p.kill()
            os.remove(PID_FILE)
        except Exception as e:
            print(f"PID Cleanup Error: {e}")

    # 2. Broad sweep for any process matching 'llama' in name or path
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            is_match = False
            pname = proc.info.get('name', '').lower()
            pexe = (proc.info.get('exe') or '').lower()
            
            if any(tn in pname for tn in target_names):
                is_match = True
            elif "llama" in pexe or "llama-server" in pexe:
                is_match = True
            
            if is_match:
                print(f"Cleaning up orphaned AI process: {proc.info['pid']} ({pname})")
                p = psutil.Process(proc.info['pid'])
                for child in p.children(recursive=True):
                    child.kill()
                p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def terminate_ai_server():
    """Unloads the model from RAM by terminating the background process."""
    global ai_ready, ai_booting
    for name, proc in list(ai_processes.items()):
        print(f"Terminating {name} AI server...")
        try:
            # Kill children first (very important for GPU offloading sub-procs)
            p = psutil.Process(proc.pid)
            for child in p.children(recursive=True):
                child.kill()
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    
    # Final sweep to ensure no ghosts remain on GPU
    cleanup_orphans()
    
    # 1.0 second delay to allow the OS to fully release port/RAM
    time.sleep(1)
    
    ai_processes.clear()
    ai_ready = False
    ai_booting = False
    log_ai_event('SHUTDOWN', 'INFO', 'AI Engine unloaded from RAM.')

def start_llama_server():
    global LAST_RESTART_TIME
    
    # Debounce: prevent spawning if we just tried very recently
    now = time.time()
    if now - LAST_RESTART_TIME < RESTART_COOLDOWN:
        print("AI Server restart suppressed (cooldown active).")
        return None
        
    # Ensure a clean slate before starting
    cleanup_orphans()
    
    # Port Guard: Check if the port is busy before trying to spawn
    if is_port_in_use(AI_CONFIG['port']):
        log_ai_event('STARTUP', 'ERROR', f"Port {AI_CONFIG['port']} is already in use. Attempting cleanup...")
        cleanup_orphans()
        time.sleep(1)
        if is_port_in_use(AI_CONFIG['port']):
            log_ai_event('STARTUP', 'ERROR', f"Port {AI_CONFIG['port']} still busy after cleanup. Aborting.")
            return None

    LAST_RESTART_TIME = now
    
    log_ai_event('STARTUP', 'INFO', f"Starting {AI_CONFIG['file']} AI server on port {AI_CONFIG['port']}...")
    model_path = os.path.join(BASE_DIR, 'models', AI_CONFIG['file'])
    
    # Redirect errors to a log file for debugging
    log_file = os.path.join(BASE_DIR, 'logs', 'llm_server_error.log')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    err_out = open(log_file, 'a', encoding='utf-8')
    
    startupinfo = None
    if os.name == 'nt' and os.path.exists(server_exe):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        cmd = [
            server_exe, 
            "-m", model_path, 
            "--port", str(AI_CONFIG['port']), 
            "--host", "127.0.0.1", 
            "-c", str(AI_CONFIG['context'])
        ]
    else:
        # Docker / Linux path: using python -m llama_cpp.server
        cmd = [
            "python3", "-m", "llama_cpp.server", 
            "--model", model_path, 
            "--port", str(AI_CONFIG['port']), 
            "--n_ctx", str(AI_CONFIG['context']),
            "--host", "127.0.0.1"
        ]
    
    proc = subprocess.Popen( # nosec B603
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=err_out,
        startupinfo=startupinfo
    )
    # Important: Close the handle in the parent process. 
    # The child process keeps its own inherited handle.
    err_out.close()
    
    # Persist the PID for next app boot recovery
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(proc.pid))
    except Exception as e:
        print(f"Error persisting AI PID: {e}")
        
    ai_processes['chat'] = proc
    return proc

def background_initialization():
    """Background task to start AI server and poll health."""
    global ai_ready, ai_booting
    ai_booting = True
    try:
        proc = start_llama_server()
        if proc is None:
            # If server didn't start (cooldown or port busy), we should not wait 2 minutes
            log_ai_event('STARTUP', 'WARNING', "AI Server startup suppressed or failed. Aborting health check.")
            ai_booting = False
            return

        url = f"http://127.0.0.1:{AI_CONFIG['port']}/health"
        max_retries = 90 # 3 minutes total for slow cold starts
        for i in range(max_retries):
            # Check if the process has already crashed/exited
            if proc.poll() is not None:
                log_ai_event('STARTUP', 'ERROR', "AI Server exited immediately after launch. Check logs/llm_server_error.log.")
                break

            try:
                # We use nosec B310 because this URL is hardcoded to localhost and safe.
                with urllib.request.urlopen(url, timeout=2) as response: # nosec B310
                    if response.status == 200:
                        ai_ready = True
                        ai_booting = False
                        log_ai_event('HEALTH', 'INFO', "AI Engine is ready and responding.")
                        break
            except Exception:
                if i % 10 == 0 and i > 0:
                    log_ai_event('HEALTH', 'WARNING', f"Still waiting for AI health check... (Attempt {i})")
                time.sleep(2)
        
        if not ai_ready:
            # Capture last 10 lines of internal log for better tracing
            error_snippet = "No error output captured."
            log_file = os.path.join(BASE_DIR, 'logs', 'llm_server_error.log')
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        error_snippet = "".join(f.readlines()[-10:])
                except Exception: pass
                
            log_ai_event('STARTUP', 'ERROR', f"AI health check timed out. Internal log tail:\n{error_snippet}")
            ai_booting = False
    except Exception as e:
        ai_booting = False
        log_ai_event('ERROR', 'ERROR', f"AI launch failed unexpectedly: {str(e)}")

def initialize_ai_system():
    """Initializes the background thread for AI boot if not already starting."""
    global ai_boot_thread, ai_booting
    
    with ai_init_lock:
        if ai_booting or ai_ready:
            return
        ai_booting = True
        
    ai_boot_thread = threading.Thread(target=background_initialization, daemon=True)
    ai_boot_thread.start()
    print("AI Background initialization started...")

def is_ai_ready():
    return ai_ready

def is_ai_booting():
    return ai_booting

def reset_activity_timer():
    global last_activity_time
    last_activity_time = time.time()

def idle_monitor():
    """Background thread to monitor inactivity and free RAM."""
    while True:
        time.sleep(60) # Heartbeat
        if ai_ready and not ai_queue.unfinished_tasks:
            idle_time = time.time() - last_activity_time
            if idle_time > IDLE_TIMEOUT:
                log_ai_event('SHUTDOWN', 'INFO', f"AI Idle for {idle_time/60:.1f} minutes. Freeing system RAM...")
                terminate_ai_server()

# Start background monitor and initial boot
threading.Thread(target=idle_monitor, daemon=True).start()
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
    snapshot = [f"### PLATFORM TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 1. System Logs (Latest Activity)
        c.execute("SELECT event_type, status, message, created_at FROM AI_System_Logs ORDER BY created_at DESC LIMIT 15")
        logs = c.fetchall()
        if logs:
            log_texts = []
            for l in logs:
                log_texts.append(f"[{l['created_at']}] {l['event_type']} ({l['status']}): {l['message']}")
            snapshot.append("### RECENT SYSTEM LOGS\n- " + "\n- ".join(log_texts))

        # 2. Recent Game Jams (with schedules)
        c.execute("SELECT title, theme, start_time, end_time FROM Game_Jams ORDER BY id DESC LIMIT 3")
        jams = c.fetchall()
        if jams:
            jam_texts = []
            for j in jams:
                jam_texts.append(f"{j['title']} (Theme: {j['theme']}, Ends: {j['end_time']})")
            snapshot.append("### RECENT JAMS\n- " + "\n- ".join(jam_texts))

        # 2. Top Games by Likes (most popular first)
        c.execute("""
            SELECT g.title, g.description, 
                   COUNT(DISTINCT gl.id) as likes,
                   COUNT(DISTINCT gc.id) as comments
            FROM Godot_Games g 
            LEFT JOIN Game_Likes gl ON gl.game_id = g.id
            LEFT JOIN Game_Comments gc ON gc.game_id = g.id
            WHERE g.validation_status = 'Validated' 
            GROUP BY g.id
            ORDER BY likes DESC, comments DESC
            LIMIT 5
        """)
        games = c.fetchall()
        if games:
            game_texts = []
            for g in games:
                desc = (g['description'][:60] + "...") if g['description'] and len(g['description']) > 60 else (g['description'] or "No description")
                game_texts.append(f"'{g['title']}': {desc} [{g['likes']} likes, {g['comments']} comments]")
            snapshot.append("### TOP GAMES BY POPULARITY\n- " + "\n- ".join(game_texts))

        # 3. Latest CV profiles
        c.execute("""
            SELECT cv.title, u.username,
                   (SELECT GROUP_CONCAT(skill) FROM (
                       SELECT json_each.value as skill
                       FROM json_each(cv.cv_data, '$.skills')
                       LIMIT 4
                   )) as top_skills
            FROM CV_Catalog cv
            JOIN Users u ON cv.user_id = u.id
            ORDER BY cv.id DESC LIMIT 5
        """)
        cvs = c.fetchall()
        if cvs:
            cv_texts = []
            for cv in cvs:
                skills = cv['top_skills'] or 'N/A'
                cv_texts.append(f"'{cv['title']}' by {cv['username']} (Skills: {skills})")
            snapshot.append("### RECENT CVs\n- " + "\n- ".join(cv_texts))

        # 4. Public Channels
        c.execute("SELECT name FROM Chat_Rooms WHERE is_enabled = 1")
        rooms = c.fetchall()
        if rooms:
            snapshot.append("### ACTIVE CHANNELS: " + ", ".join([r['name'] for r in rooms]))

        # 5. Platform totals
        c.execute("SELECT COUNT(*) FROM Users")
        total_users = (c.fetchone() or [0])[0]
        c.execute("SELECT COUNT(*) FROM Godot_Games WHERE validation_status='Validated'")
        total_games = (c.fetchone() or [0])[0]
        c.execute("SELECT COUNT(*) FROM CV_Catalog")
        total_cvs = (c.fetchone() or [0])[0]
        snapshot.append(f"### PLATFORM STATS\n- Registered Developers: {total_users}\n- Validated Games: {total_games}\n- Published CVs: {total_cvs}")

        conn.close()
    except Exception as e:
        print(f"AI Snapshot Error: {e}")
    return "\n\n".join(snapshot)


def ai_worker():
    while True:
        task = ai_queue.get()
        if task is None: break
        
        task_id, user_prompt, user_id = task
        try:
            # Update status to Waking Up if not ready
            if not ai_ready:
                with queue_lock:
                    ai_results[task_id] = {"status": "waking_up"}
                initialize_ai_system()
                # Wait for bootup - strict timeout to prevent "stuck" assistant
                max_wait = 180 # 3 minutes total
                start_wait = time.time()
                while not ai_ready:
                    if time.time() - start_wait > max_wait:
                        raise Exception("AI Engine wakeup timed out (3 minute limit reached).")
                    
                    # Heartbeat check: ensure we didn't fail and stop booting
                    if not ai_booting and not ai_ready:
                        # Attempt one last re-initialization if something died
                        initialize_ai_system()
                        time.sleep(2)
                        if not ai_booting and not ai_ready:
                            raise Exception("AI Engine failed to initialize during wakeup.")
                    time.sleep(1)

            reset_activity_timer()
            total_users, total_games, active_jam = 0, 0, "None"
            try:
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
                "You are the proglem System & Community Assistant. "
                "Provide brief, helpful, and technically accurate answers based on the system logs and community pulse provided. "
                "Do not explain your reasoning. Keep responses concise. Use following platform data strictly:\n\n"
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
            reset_activity_timer()
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
    
    # Trigger boot if idle
    if not ai_ready:
        initialize_ai_system()

    reset_activity_timer()

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