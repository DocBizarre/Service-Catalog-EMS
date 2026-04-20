import sqlite3

conn = sqlite3.connect('backend/catalog.db')

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables :", tables)

for table in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
    print(f"  {table[0]} : {count} lignes")

conn.close()