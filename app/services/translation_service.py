import threading
import urllib.request
import json
import time
from app.i18n import t, translations, save_translations
import app.i18n

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
            "message": t("Starting AI Core...")
        })

    thread = threading.Thread(target=_background_translation_job, args=(missing_keys, chunk_count), daemon=True)
    thread.start()
    return chunk_count

def _background_translation_job(all_keys, total_chunks):
    chunk_size = 15
    chunks = [all_keys[i:i + chunk_size] for i in range(0, len(all_keys), chunk_size)]
    
    for idx, keys_chunk in enumerate(chunks):
        # Update state with current progress
        with translation_lock:
            translation_state.update({
                "current": idx + 1,
                "progress_pct": int(((idx) / total_chunks) * 100),
                "message": f"{t('Processing batch')} {idx+1}/{total_chunks}..."
            })

        prompt = (
            "Translate the following UI English strings exactly to Turkish. "
            "Respond ONLY with a valid JSON object mapping the English key to the Turkish translation. "
            "No code blocks, no markdown, just RAW JSON.\nKeys:\n" + json.dumps(keys_chunk)
        )
        
        payload = {
            "model": "local-model",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.2
        }
        
        try:
            from app.services.ai_service import AI_CONFIG
            req = urllib.request.Request(
                f"http://127.0.0.1:{AI_CONFIG['port']}/v1/chat/completions",
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json", "Authorization": "Bearer admin"}
            )
            
            # Higher timeout (300s) for slow local generation on constrained hardware
            with urllib.request.urlopen(req, timeout=300) as response: # nosec B310
                result = json.loads(response.read().decode('utf-8'))
                raw_content = result['choices'][0]['message']['content']
                
                # Clean up model garbage if present (markdown blocks)
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
                
                # Save after each successful chunk
                app.i18n._dirty = True
                save_translations()
        except Exception as e:
            print(f"Error in translation batch {idx+1}: {e}")
            time.sleep(2)
            
    with translation_lock:
        translation_state.update({"status": "complete", "progress_pct": 100, "message": "Done!"})
