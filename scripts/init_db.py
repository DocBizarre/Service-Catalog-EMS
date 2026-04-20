import sqlite3
import os

DB_PATH = os.path.join('backend', 'catalog.db')
SQL_PATH = os.path.join('scripts', 'init_db.sql')

print(f"BDD : {os.path.abspath(DB_PATH)}")
print(f"SQL : {os.path.abspath(SQL_PATH)}")

with open(SQL_PATH, 'r', encoding='utf-8') as f:
    sql = f.read()

print(f"SQL chargé : {len(sql)} caractères")

conn = sqlite3.connect(DB_PATH)
conn.executescript(sql)
conn.commit()
conn.close()

print("Terminé.")