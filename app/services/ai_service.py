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
from typing import Optional, Tuple
from app.database import get_db_connection

# Integrated App Logger
logger = logging.getLogger('flask.app')

# Global Paths & Configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PID_FILE = os.path.join(BASE_DIR, 'logs', '.ai_pid')
RESTART_COOLDOWN = 10
IDLE_TIMEOUT = 7 * 60

AI_CONFIG = {
    "file": "qwen2.5-7b-instruct-q3_k_m.gguf",
    "port": 8082,
    "context": 4096,
    "threads": 6,        # Optimized for i5-1235U (2 P-cores + 4 E-cores)
    "use_gpu": False     # Set to False to force CPU / AVX2 on RAM-constrained systems
}

def validate_ai_sql(sql):
    """Strict security validator for AI-generated SQL queries."""
    sql_lower = sql.lower().strip()
    
    # 1. Start check
    if not sql_lower.startswith('select'):
        return False, "Only SELECT queries are permitted."
    
    # 2. Forbidden characters and keywords (DML/DDL/Bypass)
    # We forbid '*' to prevent bypassing column-level blocks.
    if '*' in sql_lower:
        return False, "Wildcard (*) selection is forbidden. Please list columns explicitly."
        
    forbidden = ['insert', 'update', 'delete', 'drop', 'alter', 'truncate', 'grant', 'revoke', 'replace', 'exec', 'attach', 'union']
    for word in forbidden:
        if f" {word} " in f" {sql_lower} " or sql_lower.startswith(word):
            return False, f"Forbidden SQL keyword detected: {word}"
            
    # 3. Forbidden columns/sensitive data
    sensitive = ['password_hash', 'email', 'visitor_id']
    for col in sensitive:
        if col in sql_lower:
            return False, f"Access to sensitive column '{col}' is blocked."
            
    # 4. Table whitelist
    whitelist = ['godot_games', 'game_jams', 'users', 'cv_catalog', 'game_likes', 'game_comments', 'chat_rooms', 'ai_system_logs']
    # Extract potential table names (simplified check)
    import re
    tables_found = re.findall(r'from\s+([a-zA-Z0-9_]+)', sql_lower)
    # Also check joins
    tables_found += re.findall(r'join\s+([a-zA-Z0-9_]+)', sql_lower)
    
    if not tables_found:
        return False, "No source table detected in query."
        
    for table in tables_found:
        if table not in whitelist:
            return False, f"Access to table '{table}' is blocked."
            
    return True, "OK"

# Determine server executable platform-specifically
if os.name == 'nt':
    server_exe = os.path.join(BASE_DIR, 'bin', 'llama-server.exe')
else:
    server_exe = "python3"

def ai_security_authorizer(action_code, tname, cname, sql_location, trigger_name):
    """
    Native SQLite engine-level sandbox.
    Intercepts and evaluates every operation before execution.
    """
    # Allow safe operations: SELECT statements and basic aggregate functions (COUNT, MAX)
    if action_code == sqlite3.SQLITE_SELECT or action_code == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_OK
        
    # Intercept READ access on a per-column and per-table basis
    if action_code == sqlite3.SQLITE_READ:
        table = tname.lower() if tname else ""
        col = cname.lower() if cname else ""
        
        # 1. Block sensitive columns natively
        if col in ['password_hash', 'email', 'visitor_id', 'preferences']:
            return sqlite3.SQLITE_DENY
            
        # 2. Whitelist allowed tables
        allowed_tables = [
            'godot_games', 'game_jams', 'users', 'cv_catalog', 
            'game_likes', 'game_comments', 'chat_rooms', 'ai_system_logs'
        ]
        # Allow internal SQLite tables (like sqlite_master) for schema checks if needed,
        # otherwise strictly enforce the whitelist.
        if table and table not in allowed_tables and not table.startswith('sqlite_'):
            return sqlite3.SQLITE_DENY
            
        return sqlite3.SQLITE_OK

    # Block EVERYTHING else (INSERT, DROP, UPDATE, PRAGMA, ATTACH, DELETE, etc.)
    return sqlite3.SQLITE_DENY

def execute_ai_read_query(sql: str) -> str:
    """Executes LLM queries inside a strict SQLite Authorizer sandbox."""
    if "limit" not in sql.lower():
        sql = sql.rstrip(';') + " LIMIT 15"
        
    try:
        from app.database import get_db_connection
        # We spawn a fresh connection specifically for the AI query 
        # so the strict rules don't affect standard application routing.
        conn = get_db_connection()
        
        # Attach the security sandbox to this specific connection
        conn.set_authorizer(ai_security_authorizer)
        
        c = conn.cursor()
        c.execute(sql)
        rows = c.fetchall()
        
        if not rows:
            conn.close()
            return "No results found."
            
        column_names = [d[0] for d in c.description]
        result_json = json.dumps([dict(zip(column_names, r)) for r in rows], indent=2)
        
        conn.close()
        return result_json
        
    except sqlite3.DatabaseError as e:
        # If the authorizer blocks an action, SQLite throws a DatabaseError natively
        msg = f"SECURITY BLOCK: The query attempted an unauthorized action. ({str(e)})"
        log_ai_event('SECURITY', 'WARNING', msg)
        return msg
    except Exception as e:
        return f"EXECUTION ERROR: {str(e)}"


# Engine State Management
ai_processes = {}
ai_ready = False
ai_booting = False
ai_boot_thread = None
ai_init_lock = threading.Lock()
LAST_RESTART_TIME = 0.0
last_activity_time = time.time()

def log_ai_event(event_type: str, status: str, message: str) -> None:
    """Logs an AI event to both the integrated logger and DB logs."""
    log_msg = f"[AI {event_type}] ({status}) {message}"
    if status == 'ERROR':
        logger.error(log_msg)
    elif status == 'WARNING':
        logger.warning(log_msg)
    else:
        logger.info(log_msg)

    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO AI_System_Logs (event_type, status, message, created_at) VALUES (?, ?, ?, ?)",
            (event_type, status, message, now)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log failure: {e}")

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def cleanup_orphans() -> None:
    """Kills orphaned llama-server processes to reclaim RAM/GPU."""
    try:
        import requests
        res = requests.get(f"http://127.0.0.1:{AI_CONFIG['port']}/health", timeout=1)
        if res.status_code == 200:
            return
    except:
        pass

    target_names = ["llama-server.exe", "llama-server"]
    
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
                if psutil.pid_exists(old_pid):
                    p = psutil.Process(old_pid)
                    if any(tn in p.name().lower() for tn in target_names):
                        for child in p.children(recursive=True):
                            child.kill()
                        p.kill()
            os.remove(PID_FILE)
        except Exception: pass

    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            pname = proc.info.get('name', '').lower()
            pexe = (proc.info.get('exe') or '').lower()
            if any(tn in pname for tn in target_names) or "llama" in pexe:
                p = psutil.Process(proc.info['pid'])
                for child in p.children(recursive=True):
                    child.kill()
                p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def terminate_ai_server() -> None:
    """Unloads the model from RAM by terminating the background process."""
    global ai_ready, ai_booting
    for proc in list(ai_processes.values()):
        try:
            p = psutil.Process(proc.pid)
            for child in p.children(recursive=True):
                child.kill()
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try: proc.kill()
            except Exception: pass
    
    cleanup_orphans()
    time.sleep(1)
    
    ai_processes.clear()
    ai_ready = ai_booting = False
    log_ai_event('SHUTDOWN', 'INFO', 'AI Engine unloaded from RAM.')

def start_llama_server() -> Optional[subprocess.Popen]:
    global LAST_RESTART_TIME
    now = time.time()
    if now - LAST_RESTART_TIME < RESTART_COOLDOWN:
        return None

    cleanup_orphans()
    time.sleep(1) # Reduced from 3s to speed up cold start
    if is_port_in_use(AI_CONFIG['port']):
        log_ai_event('STARTUP', 'ERROR', f"Port {AI_CONFIG['port']} occupied.")
        return None

    mem = psutil.virtual_memory()
    free_gb = mem.available / (1024**3)
    # Lenient RAM check: warn if < 4GB, block only if < 1GB to prevent OOM.
    if free_gb < 1.0:
        log_ai_event('STARTUP', 'ERROR', f"Critically low RAM to start AI. Available: {free_gb:.1f}GB. Required: >1.0GB")
        return None
    elif free_gb < 4.0:
        log_ai_event('STARTUP', 'WARNING', f"RAM is tight ({free_gb:.1f}GB available). Swapping might occur.")

    LAST_RESTART_TIME = now
    model_path = os.path.join(BASE_DIR, 'models', AI_CONFIG['file'])
    log_file = os.path.join(BASE_DIR, 'logs', 'llm_server_error.log')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    startupinfo = None
    if os.name == 'nt' and os.path.exists(server_exe):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Build command with optimized threads and GPU layers
        cmd = [
            server_exe, 
            "-m", model_path, 
            "--port", str(AI_CONFIG['port']), 
            "--host", "127.0.0.1", 
            "-c", str(AI_CONFIG['context']),
            "-t", str(AI_CONFIG['threads']),
            "--flash-attn", "off"
        ]
        
        # If use_gpu is False, we force CPU by setting gpu layers to 0
        if not AI_CONFIG.get('use_gpu', True):
            cmd += ["--n-gpu-layers", "0"]
            
    else:
        cmd = [
            "python3", "-m", "llama_cpp.server", 
            "--model", model_path, 
            "--port", str(AI_CONFIG['port']), 
            "--n_ctx", str(AI_CONFIG['context']), 
            "--host", "127.0.0.1",
            "--threads", str(AI_CONFIG['threads']),
            "--flash-attn", "off"
        ]
        if not AI_CONFIG.get('use_gpu', True):
            cmd += ["--n_gpu_layers", "0"]
    
    with open(log_file, 'a', encoding='utf-8') as err_out:
        proc = subprocess.Popen( # nosec B603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=err_out,
            startupinfo=startupinfo
        )
        # Important: Close the handle in the parent process. 
        # The child process keeps its own inherited handle.
        err_out.close()
        
        log_ai_event('STARTUP', 'INFO', f"AI process spawned with PID {proc.pid}")
        
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(proc.pid))
    except Exception: pass
        
    ai_processes['chat'] = proc
    return proc

def background_initialization() -> None:
    global ai_ready, ai_booting
    ai_booting = True
    try:
        url = f"http://127.0.0.1:{AI_CONFIG['port']}/health"
        
        # Cross-process check: if port is already active, verify health.
        if is_port_in_use(AI_CONFIG['port']):
            try:
                with urllib.request.urlopen(url, timeout=1.5) as response: # nosec B310
                    if response.status == 200:
                        ai_ready = True
                        ai_booting = False
                        log_ai_event('HEALTH', 'INFO', "AI Engine detected as already running.")
                        return
            except Exception:
                log_ai_event('PORT_CONFLICT', 'WARNING', f"Port {AI_CONFIG['port']} is in use but unresponsive. Attempting to reclaim...")
                # Attempt to kill whatever is on the port
                try:
                    for proc in psutil.process_iter(['pid', 'name']):
                        for conn in proc.connections(kind='inet'):
                            if conn.laddr.port == AI_CONFIG['port']:
                                p = psutil.Process(proc.info['pid'])
                                log_ai_event('PORT_CONFLICT', 'INFO', f"Killing process {p.pid} ({p.name()}) occupying AI port.")
                                p.kill()
                                time.sleep(1)
                except Exception as ex:
                    log_ai_event('PORT_CONFLICT', 'ERROR', f"Failed to reclaim port: {ex}")

        proc = start_llama_server()
        if proc is None:
            # Last-ditch check in case it started between checks
            if is_port_in_use(AI_CONFIG['port']):
                try:
                    with urllib.request.urlopen(url, timeout=3) as response: # nosec B310
                        if response.status == 200:
                            ai_ready = True
                            ai_booting = False
                            return
                except Exception: pass
            
            ai_booting = False
            return

        url = f"http://127.0.0.1:{AI_CONFIG['port']}/health"
        max_retries = 90
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
            except Exception as e:
                if i % 10 == 0 and i > 0:
                    log_ai_event('HEALTH', 'WARNING', f"Still waiting for AI health check... (Attempt {i}, Error: {e})")
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
    """Checks if the AI engine is ready. Verifies the port to sync state across processes."""
    global ai_ready
    if ai_ready:
        return True
    
    # Ping the local server to verify status
    try:
        url = f"http://127.0.0.1:{AI_CONFIG['port']}/health"
        with urllib.request.urlopen(url, timeout=0.5) as response: # nosec B310
            if response.status == 200:
                ai_ready = True
                return True
    except Exception:
        pass
    return False

def is_ai_booting():
    return ai_booting

def reset_activity_timer():
    global last_activity_time
    last_activity_time = time.time()

def check_idle_timeout():
    """Checks if the AI engine has been idle and terminates it if so."""
    if not ai_ready:
        return

    idle_duration = time.time() - last_activity_time
    if idle_duration > IDLE_TIMEOUT:
        log_ai_event('SHUTDOWN', 'INFO', f"AI Engine idle for {int(idle_duration/60)}m. Unloading to free RAM.")
        terminate_ai_server()

# Note: Background monitor and initial boot moved to standalone bin/worker.py or handled on-demand.
# However, we keep helper functions for use by both the web app and the worker.

@atexit.register
def cleanup_servers():

    for proc in list(ai_processes.values()):
        print("Terminating AI server...")
        proc.terminate()

        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

# No-op placeholders for compatibility during transition
def cleanup_old_results():
    pass

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
            SELECT g.id, g.title, g.description, 
                   COUNT(DISTINCT gl.id) as likes,
                   COUNT(DISTINCT gc.id) as comments
            FROM Godot_Games g 
            LEFT JOIN Game_Likes gl ON gl.game_id = g.id
            LEFT JOIN Game_Comments gc ON gc.game_id = g.id
            WHERE g.validation_status = 'Approved' 
            GROUP BY g.id
            ORDER BY likes DESC, comments DESC
            LIMIT 5
        """)
        games = c.fetchall()
        if games:
            game_texts = []
            for g in games:
                desc = (g['description'][:60] + "...") if g['description'] and len(g['description']) > 60 else (g['description'] or "No description")
                game_texts.append(f"ID {g['id']} - '{g['title']}': {desc} [{g['likes']} likes, {g['comments']} comments]")
            snapshot.append("### TOP GAMES BY POPULARITY\n- " + "\n- ".join(game_texts))

        # 3. Latest CV profiles
        c.execute("SELECT id, title, user_id FROM CV_Catalog ORDER BY id DESC LIMIT 5")
        cvs = c.fetchall()
        if cvs:
            cv_texts = []
            for cv in cvs:
                cv_texts.append(f"ID {cv['id']} - '{cv['title']}'")
            snapshot.append("### RECENT CVs\n- " + "\n- ".join(cv_texts))

        # 4. Public Channels
        c.execute("SELECT id, name FROM Chat_Rooms WHERE is_enabled = 1")
        rooms = c.fetchall()
        if rooms:
            snapshot.append("### ACTIVE CHANNELS: " + ", ".join([f"{r['name']} (ID {r['id']})" for r in rooms]))

        # 5. Platform totals
        c.execute("SELECT COUNT(*) FROM Users")
        total_users = (c.fetchone() or [0])[0]
        c.execute("SELECT COUNT(*) FROM Godot_Games WHERE validation_status='Approved'")
        total_games = (c.fetchone() or [0])[0]
        snapshot.append(f"### PLATFORM STATS\n- Registered Developers: {total_users}\n- Validated Games: {total_games}")

        conn.close()
    except Exception as e:
        print(f"AI Snapshot Error: {e}")
    return "\n\n".join(snapshot)

def get_platform_schema():
    """Provides a concise schema overview for AI query generation."""
    return """
--- CORE DATABASE SCHEMA ---
- Table: Godot_Games (id, user_id, jam_id, title, description, game_url, validation_status, views, created_at)
- Table: Game_Jams (id, title, theme, start_time, end_time, youtube_url)
- Table: Users (id, username, created_at)
- Table: CV_Catalog (id, user_id, title, summary, cv_data [JSON], created_at)
- Table: Game_Likes (id, user_id, game_id, created_at)
- Table: Game_Comments (id, user_id, game_id, content, created_at)
- Table: Chat_Rooms (id, name, is_enabled, created_at)
- Table: AI_System_Logs (id, event_type, status, message, created_at)
---------------------------
"""

def process_ai_task(task_id, payload_dict):
    """
    Core AI inference logic. Extracted for use by the standalone worker.
    """
    user_prompt = payload_dict.get('prompt', '')
    user_id = payload_dict.get('user_id', 'unknown')
    
    try:
        # Update status to Waking Up if not ready
        if not is_ai_ready():
            conn = get_db_connection()
            conn.execute("UPDATE System_Tasks SET status = 'waking_up' WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            
            initialize_ai_system()
            # Wait for bootup - strict timeout to prevent "stuck" assistant
            max_wait = 180 # 3 minutes total
            start_wait = time.time()
            while not is_ai_ready():
                if time.time() - start_wait > max_wait:
                    raise Exception("AI Engine wakeup timed out (3 minute limit reached).")
                
                # Heartbeat check: ensure we didn't fail and stop booting
                if not is_ai_booting() and not is_ai_ready():
                    # Attempt one last re-initialization if something died
                    initialize_ai_system()
                    time.sleep(2)
                    if not is_ai_booting() and not is_ai_ready():
                        raise Exception("AI Engine failed to initialize during wakeup.")
                time.sleep(1)

        reset_activity_timer()
        
        # PHASE 0: Fetch Conversation History (Last 3 rounds)
        history_msgs = []
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT payload, result FROM System_Tasks 
                WHERE user_id = ? AND task_type = 'ai_chat' AND status = 'done' 
                ORDER BY created_at DESC LIMIT 3
            """, (user_id,))
            history_rows = cursor.fetchall()[::-1] # Reverse to get chronological order
            for row in history_rows:
                old_payload = json.loads(row['payload'])
                old_result = json.loads(row['result'])
                history_msgs.append({"role": "user", "content": old_payload.get('prompt', '')})
                history_msgs.append({"role": "assistant", "content": old_result.get('answer', '')})
            conn.close()
        except Exception as e:
            print(f"History fetch error: {e}")

        # PHASE 1: Thinking Pass (Determine if we need more data)
        community_data = get_public_snapshot()
        platform_schema = get_platform_schema()
        
        sys_msg = (
            "You are the proglem Data-Aware Assistant for the 'proglem' ecosystem. "
            "Context: This is a high-performance platform for hosting Godot WebGL games and interactive CVs. "
            "Hardware Constraints: 16GB RAM (8GB limit for production), SQLite (WAL) backend. "
            "Games: All games are Godot WebGL binaries hosted locally on our cloud. "
            "You have access to a live SQLite database with these tables:\n"
            f"{platform_schema}\n"
            "You also have a snapshot of recent activity:\n"
            f"{community_data}\n\n"
            "STRICT INSTRUCTIONS:\n"
            "1. NO EXTERNAL REDIRECTS: Do NOT suggest users play games on Itch.io or other websites. Every game mentioned in our database is playable directly here. "
            "2. If the user asks for info NOT in the snapshot (e.g., specific game IDs, user records, or platform history), "
            "you MUST respond with a SQL query wrapped in <sql>SELECT ...</sql> tags.\n"
            "3. LINKING: Use Markdown for platform resources ONLY if you have a valid numerical ID. Replace the ID in these patterns:\n"
            "   - Games: [Title](/games/123) (EXAMPLE: [My Godot Game](/games/1))\n"
            "   - CV Profiles: [Title](/cv/45)\n"
            "   - Chat Rooms: [Name](/chat?room_id=7)\n"
            "   - Users: [Username](/u/alice)\n"
            "4. GODOT/WEBGL: When users ask about games, assume they are talking about the Godot WebGL games on THIS platform. Never tell them to go to Itch.io. "
            "5. IMPORTANT: NEVER use '?' or '{id}' or any placeholder in a link. If you don't have the ID, use <sql> to find it first.\n"
            "6. NO HALLUCINATION: Never share raw file paths like '/play_mock/...' or internal S3 URLs. Only use the patterns in rule #3.\n"
            "7. DATABASE QUERIES: When using <sql> tags, you MUST list specific column names (e.g., SELECT id, title FROM Godot_Games). NEVER use '*' (wildcard) as it is strictly blocked for security. "
            "The 'id' column is essential for building links but should NOT be shown to the user as raw text. Use it only inside Markdown patterns.\n"
            "8. ALL GAMES: The 'Godot_Games' table contains ALL games on the platform, including those submitted to Game Jams (identifiable via jam_id). "
            "Always filter Godot_Games by validation_status = 'Approved' to ensure you only show playable games.\n"
            "9. Be concise, technical, and directly answer the user."
        )

        def call_ai(msgs, stream=False):
            import requests
            payload = {
                "model": "local-model",
                "messages": msgs,
                "max_tokens": 700,
                "temperature": 0.3,
                "stream": stream
            }
            server_url = f"http://127.0.0.1:{AI_CONFIG['port']}/v1/chat/completions"
            
            if not stream:
                res = requests.post(server_url, json=payload, timeout=120)
                return res.json()['choices'][0]['message']['content']
            
            # Streaming implementation
            full_text = ""
            last_update = time.time()
            
            with requests.post(server_url, json=payload, stream=True, timeout=120) as r:
                for line in r.iter_lines():
                    if line:
                        line_text = line.decode('utf-8')
                        if line_text.startswith("data: "):
                            data_str = line_text[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk['choices'][0].get('delta', {}).get('content', '')
                                full_text += content
                                
                                # Update DB every 0.8 seconds to create typing effect without overloading DB
                                if time.time() - last_update > 0.8:
                                    conn = get_db_connection()
                                    conn.execute(
                                        "UPDATE System_Tasks SET result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                        (json.dumps({"answer": full_text}), task_id)
                                    )
                                    conn.commit()
                                    conn.close()
                                    last_update = time.time()
                            except:
                                continue
            return full_text

        # First Pass
        first_pass_msgs = [{"role": "system", "content": sys_msg}] + history_msgs + [{"role": "user", "content": user_prompt}]
        initial_response = call_ai(first_pass_msgs)
        
        # Check for SQL tag
        import re
        sql_match = re.search(r'<sql>(.*?)</sql>', initial_response, re.DOTALL | re.IGNORECASE)
        
        if sql_match:
            sql_query = sql_match.group(1).strip()
            
            conn = get_db_connection()
            conn.execute("UPDATE System_Tasks SET status = 'generating', result = ? WHERE id = ?", (json.dumps({"answer": f"🔍 Searching database for: `{sql_query}`..."}), task_id))
            conn.commit()
            conn.close()
            
            query_results = execute_ai_read_query(sql_query)
            
            # Second Pass: Final Answer
            final_sys_msg = (
                "You are the proglem Data-Aware Assistant. Use these search results to answer the user.\n"
                f"SEARCH RESULTS:\n{query_results}\n\n"
                "INSTRUCTIONS:\n"
                "1. Provide a direct, helpful answer based on the search results.\n"
                "2. Use Markdown links for platform resources: [Title](/games/ID), [Title](/cv/ID), [Name](/chat?room_id=ID), [Username](/u/name).\n"
                "3. IMPORTANT: Use the actual numerical 'id' column from the search results to build the links. NEVER use placeholders.\n"
                "4. If a result exists but you are missing the title, use a generic name but keep the ID valid."
            )
            
            conn = get_db_connection()
            conn.execute("UPDATE System_Tasks SET status = 'generating', result = ? WHERE id = ?", (json.dumps({"answer": "Analysing data..."}), task_id))
            conn.commit()
            conn.close()
            
            final_pass_msgs = [{"role": "system", "content": final_sys_msg}] + history_msgs + [{"role": "user", "content": user_prompt}]
            full_answer = call_ai(final_pass_msgs, stream=True)
        else:
            conn = get_db_connection()
            conn.execute("UPDATE System_Tasks SET status = 'generating' WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            final_pass_msgs = [{"role": "system", "content": sys_msg}] + history_msgs + [{"role": "user", "content": user_prompt}]
            full_answer = call_ai(final_pass_msgs, stream=True)

        return {"status": "done", "answer": full_answer}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            conn = get_db_connection()
            error_json = json.dumps({"answer": f"⚠️ AI Engine error: {str(e)}"})
            conn.execute("UPDATE System_Tasks SET status = 'error', result = ? WHERE id = ?", (error_json, task_id))
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"Failed to update task error state: {db_err}")
            
        return {"status": "error", "message": str(e)}

# Note: threading.Thread(target=ai_worker, daemon=True).start() removed.
# This logic is now handled in bin/worker.py

def submit_prompt(user_id, prompt):
    task_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": prompt, "user_id": user_id})
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE System_Tasks 
            SET status = 'error', result = '{"answer": "Task timed out and was cleared."}' 
            WHERE status IN ('pending', 'waking_up', 'thinking', 'generating') 
            AND created_at < datetime('now', '-5 minutes')
        """)
        conn.commit()

        cursor.execute(
            "SELECT id FROM System_Tasks WHERE user_id = ? AND status IN ('pending', 'waking_up', 'thinking', 'generating')", 
            (user_id,)
        )
        if cursor.fetchone():
            return None, False

        cursor.execute(
            "INSERT INTO System_Tasks (id, user_id, task_type, payload, status) VALUES (?, ?, 'ai_chat', ?, 'thinking')",
            (task_id, user_id, payload)
        )
        conn.commit()
        
        # Calculate dynamic queue position
        # We count everything that is not 'done' or 'error' and was created before or at the same time as this task
        cursor.execute("""
            SELECT COUNT(*) FROM System_Tasks 
            WHERE status NOT IN ('done', 'error') 
            AND created_at <= (SELECT created_at FROM System_Tasks WHERE id = ?)
        """, (task_id,))
        position = cursor.fetchone()[0]
        
        return task_id, position > 1
    finally:
        conn.close()

def get_result(task_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, result, created_at FROM System_Tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if not row:
            return {"status": "not_found"}
            
        status = row['status']
        result_data = json.loads(row['result']) if row['result'] else {}
        
        if status == 'thinking':
            # Dynamic queue position calculation
            # Count all tasks ahead of us that are still being processed
            cursor.execute("""
                SELECT COUNT(*) FROM System_Tasks 
                WHERE status NOT IN ('done', 'error') 
                AND created_at <= ?
            """, (row['created_at'],))
            result_data['queue_pos'] = cursor.fetchone()[0]
            
        return {"status": status, **result_data}
    finally:
        conn.close()