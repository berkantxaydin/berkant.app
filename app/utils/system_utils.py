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
        # Get memory for the chat process if active
        proc = ai_processes.get('chat')
        if proc and proc.poll() is None:
            p = psutil.Process(proc.pid)
            ai_ram_mb = p.memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    
    # User has 8GB RAM budget on deployment server
    budget_mb = 8192
    global_ram_percent = sys_ram.percent
    ai_ram_percent = min((ai_ram_mb / budget_mb) * 100, 100)
    
    return {
        "cpu_usage": cpu_usage,
        "ram_used_gb": sys_ram.used / (1024**3),
        "ram_total_gb": 8.0, # Budgeted
        "ram_percent": global_ram_percent,
        "ai_ram_mb": ai_ram_mb,
        "ai_ram_percent": ai_ram_percent,
        "sys_ram_gb": max(0, (sys_ram.used/1024**3) - (ai_ram_mb/1024))
    }
