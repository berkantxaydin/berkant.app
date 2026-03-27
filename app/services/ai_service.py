import queue
import threading
import uuid
import os
import subprocess
import time
import urllib.request
import json
import atexit

# Global paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
server_exe = os.path.join(BASE_DIR, 'bin', 'llama-server.exe')
model_path = os.path.join(BASE_DIR, 'models', 'LFM2.5-1.2B-Thinking-Q4_k_m.gguf')
SERVER_URL = "http://127.0.0.1:8081/v1/chat/completions"

# 1. Automatically manage the local llama-server in the background
llama_process = None

def start_llama_server():
    global llama_process
    print("Starting integrated LLM server...")
    # Hide window creation on Windows
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    llama_process = subprocess.Popen( # nosec B603
        [server_exe, "-m", model_path, "--port", "8081", "-c", "2048"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo
    )
    print("LLM server spawned! Waiting for boot...")
    time.sleep(3)  # Give it a moment to load the model into memory

start_llama_server()

# Ensure the server closes when the python app exits
@atexit.register
def cleanup_server():
    if llama_process:
        print("Terminating LLM server...")
        llama_process.terminate()
        llama_process.wait()

ai_queue = queue.Queue()
ai_results = {}

def ai_worker():
    """Background worker to ensure we only use CPU/RAM for one chat at a time."""
    while True:
        task = ai_queue.get()
        if task is None: break
        
        task_id, user_prompt = task
        try:
            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant for the proglem platform. You help users with CVs and Godot games and Rimworld."},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 512,
                "temperature": 0.7,
                "stream": True
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer local"})
            
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
                            delta = chunk_json['choices'][0]['delta']
                            if 'content' in delta:
                                full_answer += delta['content']
                        except Exception as e:
                            print(f"[LLM] Stream decoding error: {e}")
            
            ai_results[task_id] = {"status": "done", "answer": full_answer}
        except Exception as e:
            import traceback
            traceback.print_exc()
            ai_results[task_id] = {"status": "error", "message": str(e)}
        finally:
            ai_queue.task_done()

# Start the worker thread
threading.Thread(target=ai_worker, daemon=True).start()

def submit_prompt(prompt):
    task_id = str(uuid.uuid4())
    ai_results[task_id] = {"status": "thinking"}
    
    is_busy = not ai_queue.empty()
    ai_queue.put((task_id, prompt))
    
    return task_id, is_busy

def get_result(task_id):
    return ai_results.get(task_id, {"status": "not_found"})
