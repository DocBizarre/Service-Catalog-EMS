import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'backend', 'catalog.db')
SQL_PATH = os.path.join(os.path.dirname(__file__), 'init_db.sql')

with open(SQL_PATH, 'r', encoding='utf-8') as f:
    sql = f.read()

conn = sqlite3.connect(DB_PATH)
conn.executescript(sql)
conn.commit()
conn.close()

print("Base de données créée.")