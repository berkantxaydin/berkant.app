import os
import sys
import sqlite3
import logging

# Ensure absolute path to project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from app.database import init_db, get_db_connection

logging.basicConfig(level=logging.INFO)

print("--- Database Verification ---")
try:
    print("Running init_db()...")
    init_db()
    print("init_db() execution finished.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check for Analytics_Logs table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Analytics_Logs';")
    if cursor.fetchone():
        print("[SUCCESS] Analytics_Logs table exists.")
    else:
        print("[FAILURE] Analytics_Logs table is missing!")
        
    # Check for indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_analytics_path';")
    if cursor.fetchone():
        print("[SUCCESS] idx_analytics_path index exists.")
    else:
        print("[FAILURE] idx_analytics_path index is missing!")

    conn.close()
except Exception as e:
    print(f"[ERROR] Verification failed: {e}")
