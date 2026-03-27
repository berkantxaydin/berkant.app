import os
import time
import socket
import subprocess
import sys

def is_port_in_use(port, host='127.0.0.1'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def run_desktop():
    """
    Spawns the Flask `proglem` WSGI app.
    Decouples cleanly if the public website backend is currently monopolizing port 5000 securely.
    """
    if not is_port_in_use(5000):
        print("Mounting strictly Headless OS Website Server...")
        # 0x00000008 translates natively to DETACHED_PROCESS on the core Windows API
        subprocess.Popen([sys.executable, "headless.py"], creationflags=0x00000008)
        time.sleep(3)  
    else:
        print("Port 5000 actively locked. Binding purely as a Native UI Thin Client!")
    
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    # Prefer Edge (always on Win10/11) or fallback to Chrome
    browser_exe = edge_path if os.path.exists(edge_path) else chrome_path
    
    print(f"Executing OS Window via {browser_exe}...")
    subprocess.run([
        browser_exe,
        "--app=http://127.0.0.1:5000",
        "--window-size=1280,800"
    ])

if __name__ == '__main__':
    run_desktop()
