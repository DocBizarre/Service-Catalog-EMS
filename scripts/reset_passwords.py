import sqlite3
import bcrypt

conn = sqlite3.connect('backend/catalog.db')

# Remettre en clair puis hasher
users = [('admin', 'changeme'), ('manager', 'changeme'), ('collab', 'changeme')]

for username, password in users:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
    print(f"{username} : mot de passe hashé")

conn.commit()
conn.close()
print("Terminé.")