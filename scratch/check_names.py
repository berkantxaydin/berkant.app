import sqlite3
conn = sqlite3.connect('db/proglem.db')
conn.row_factory = sqlite3.Row
for r in conn.execute('SELECT name FROM Chat_Rooms'):
    print(repr(r['name']).encode('utf-8'))
conn.close()
