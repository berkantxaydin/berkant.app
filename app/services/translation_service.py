import threading
import urllib.request
import json
import time
import uuid
from app.i18n import t, translations, save_translations
import app.i18n
from app.database import get_db_connection

# Global state for background translation tracking
translation_state = {"status": "idle", "current": 0, "total": 0, "progress_pct": 0, "message": ""}
translation_lock = threading.Lock()

def get_translation_state():
    with translation_lock:
        return translation_state.copy()

def reset_translation_state():
    with translation_lock:
        translation_state["status"] = "idle"

def start_translation_job(missing_keys):
    """Initializes and starts the background translation thread."""
    chunk_count = (len(missing_keys) + 14) // 15
    with translation_lock:
        translation_state.update({
            "status": "running",
            "current": 0,
            "total": chunk_count,
            "progress_pct": 0,
            "message": t("Queueing translation tasks...")
        })

    thread = threading.Thread(target=_background_translation_job, args=(missing_keys, chunk_count), daemon=True)
    thread.start()
    return chunk_count

def _background_translation_job(all_keys, total_chunks):
    chunk_size = 15
    chunks = [all_keys[i:i + chunk_size] for i in range(0, len(all_keys), chunk_size)]
    
    task_ids = []
    conn = get_db_connection()
    try:
        for idx, keys_chunk in enumerate(chunks):
            task_id = str(uuid.uuid4())
            payload = json.dumps({"keys": keys_chunk, "batch_idx": idx, "total_batches": total_chunks})
            conn.execute(
                "INSERT INTO System_Tasks (id, task_type, payload, status) VALUES (?, 'ai_translation', ?, 'pending')",
                (task_id, payload)
            )
            task_ids.append(task_id)
        conn.commit()
    finally:
        conn.close()

    # Monitor tasks
    completed = 0
    while completed < len(task_ids):
        completed = 0
        current_batch_msg = ""
        
        conn = get_db_connection()
        try:
            for tid in task_ids:
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM System_Tasks WHERE id = ?", (tid,))
                row = cursor.fetchone()
                if row and row[0] in ['done', 'error']:
                    completed += 1
                elif row and row[0] == 'generating':
                    current_batch_msg = f"Processing batch {task_ids.index(tid)+1}/{total_chunks}..."
        finally:
            conn.close()

        with translation_lock:
            translation_state.update({
                "current": completed,
                "progress_pct": int((completed / len(task_ids)) * 100),
                "message": current_batch_msg or f"Waiting in queue ({completed}/{total_chunks} done)..."
            })
        
        if completed < len(task_ids):
            time.sleep(2)

    with translation_lock:
        translation_state.update({"status": "complete", "progress_pct": 100, "message": "Done!"})

def process_translation_batch(task_id, payload):
    """
    Executed by the worker. respect RAM Rule.
    """
    keys_chunk = payload.get('keys', [])
    
    prompt = (
        "Translate the following UI English strings exactly to Turkish. "
        "Respond ONLY with a valid JSON object mapping the English key to the Turkish translation. "
        "No code blocks, no markdown, just RAW JSON.\nKeys:\n" + json.dumps(keys_chunk)
    )
    
    ai_payload = {
        "model": "local-model",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.2
    }
    
    from app.services.ai_service import AI_CONFIG, is_ai_ready, initialize_ai_system
    
    if not is_ai_ready():
        initialize_ai_system()
        # Wait for bootup
        start_wait = time.time()
        while not is_ai_ready() and time.time() - start_wait < 120:
            time.sleep(1)

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{AI_CONFIG['port']}/v1/chat/completions",
            data=json.dumps(ai_payload).encode('utf-8'),
            headers={"Content-Type": "application/json", "Authorization": "Bearer admin"}
        )
        
        with urllib.request.urlopen(req, timeout=300) as response: # nosec B310
            result = json.loads(response.read().decode('utf-8'))
            raw_content = result['choices'][0]['message']['content']
            
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[-1].split("```")[0]
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[-1].split("```")[0]
            
            new_translations = json.loads(raw_content.strip())
            
            with app.i18n._i18n_lock:
                if 'tr' not in translations: 
                    translations['tr'] = {}
                    
                for k, v in new_translations.items():
                    if k in keys_chunk:
                        translations['tr'][k] = v
            
            app.i18n._dirty = True
            save_translations()
            return {"status": "done"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
