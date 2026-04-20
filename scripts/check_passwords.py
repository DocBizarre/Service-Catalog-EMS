import sqlite3

conn = sqlite3.connect('backend/catalog.db')
users = conn.execute("SELECT username, password FROM users").fetchall()
for username, password in users:
    print(f"{username} : {password[:30]}...")
conn.close()