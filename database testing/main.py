import sqlite3
import os

# Always use the path of THIS script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

print("Using database at:", DB_PATH)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON;")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    hwid TEXT NOT NULL,
    notes TEXT
);
''')

cursor.execute('''
INSERT INTO users (username, password, hwid, notes)
VALUES (?, ?, ?, ?)
''', ("test_user", "hashed_pw", "abc123", "Testing proper path"))

conn.commit()

cursor.execute("SELECT * FROM users;")
print("Current rows:", cursor.fetchall())

conn.close()
