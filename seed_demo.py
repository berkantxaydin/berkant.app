import sqlite3

conn = sqlite3.connect('proglem.db')
try:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Users LIMIT 1")
    user = cursor.fetchone()
    if user:
        uid = user[0]
        # check if it already exists
        cursor.execute("SELECT id FROM Godot_Games WHERE game_url = '/mock_game/Pong%20Multiplayer.html'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO Godot_Games (user_id, title, description, game_url, validation_status) VALUES (?, 'Pong Multiplayer (Demo)', 'Official Demo WebGL Game fallback', '/mock_game/Pong%20Multiplayer.html', 'Approved')", (uid,))
            conn.commit()
            print("Seeded demo game!")
except Exception as e:
    print(e)
conn.close()
