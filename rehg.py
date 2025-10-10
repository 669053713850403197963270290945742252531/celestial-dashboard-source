import sqlite3
conn = sqlite3.connect("users.db")
cur = conn.cursor()
cur.execute("SELECT id, username, password, hwid FROM users WHERE username='corrade'")
print(cur.fetchone())
conn.close()