import sqlite3
from app.database import init_db

init_db()
conn = sqlite3.connect('proglem.db')
try:
    conn.execute('ALTER TABLE Godot_Games ADD COLUMN jam_id INTEGER REFERENCES Game_Jams(id)')
    conn.commit()
except sqlite3.OperationalError as e:
    print('Alter table error (might exist already):', e)

try:
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM Game_Jams')
    if cursor.fetchone()[0] == 0:
        conn.execute("INSERT INTO Game_Jams (title, theme, start_time, end_time, youtube_url) VALUES ('Proglem Genesis Jam', 'Classic', datetime('now', '-1 day'), datetime('now', '+7 days'), 'https://www.youtube.com/embed/dQw4w9WgXcQ')")
        conn.commit()
        print("Seeded game jam!")
except Exception as e:
    print("Seed error:", e)
conn.close()
