import psutil
import time as _time
from typing import Dict, Any

def get_system_metrics() -> Dict[str, Any]:
    """Gather real-time system metrics including CPU and RAM usage."""
    cpu_usage = psutil.cpu_percent(interval=0.5)
    sys_ram = psutil.virtual_memory()
    
    # AI Specific Metrics
    ai_ram_mb = 0
    try:
        from app.services.ai_service import ai_processes
        # 1. Try local process handle (if started by this process)
        proc = ai_processes.get('chat')
        if proc and proc.poll() is None:
            p = psutil.Process(proc.pid)
            ai_ram_mb = p.memory_info().rss / (1024 * 1024)
        else:
            # 2. Fallback: Search system for any llama-server process
            # (Started by worker or previous crash)
            target_names = ["llama-server.exe", "llama-server"]
            for p in psutil.process_iter(['name', 'memory_info']):
                try:
                    if any(tn in p.info['name'].lower() for tn in target_names):
                        ai_ram_mb += p.info['memory_info'].rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
    except Exception:
        pass
    
    # User machine has ~16GB RAM
    total_ram_gb = sys_ram.total / (1024**3)
    global_ram_percent = sys_ram.percent
    
    # AI RAM percentage relative to the TOTAL system RAM
    ai_ram_percent = (ai_ram_mb / (sys_ram.total / (1024*1024))) * 100
    # System RAM (excluding AI) percentage
    sys_only_percent = max(0, global_ram_percent - ai_ram_percent)
    
    return {
        "cpu_usage": cpu_usage,
        "ram_used_gb": sys_ram.used / (1024**3),
        "ram_total_gb": total_ram_gb,
        "ram_percent": global_ram_percent,
        "ai_ram_mb": ai_ram_mb,
        "ai_ram_percent": ai_ram_percent,
        "sys_only_percent": sys_only_percent,
        "sys_ram_gb": max(0, (sys_ram.used/1024**3) - (ai_ram_mb/1024))
    }
