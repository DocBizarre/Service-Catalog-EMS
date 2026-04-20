-- Table des applications
CREATE TABLE IF NOT EXISTS apps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    icon        TEXT,
    description TEXT,
    tag         TEXT,
    online      INTEGER DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL CHECK(role IN ('admin','manager','collab')),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table des permissions (quelle app est accessible à quel rôle)
CREATE TABLE IF NOT EXISTS permissions (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id  INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    role    TEXT NOT NULL CHECK(role IN ('admin','manager','collab'))
);

-- Table des favoris (par utilisateur)
CREATE TABLE IF NOT EXISTS favorites (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app_id  INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    UNIQUE(user_id, app_id)
);

-- Table d'audit (journal des connexions)
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id),
    action     TEXT NOT NULL,
    detail     TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Données de démonstration
INSERT INTO apps (name, url, icon, tag) VALUES
    ('Google Workspace', 'https://workspace.google.com', '📧', 'Général'),
    ('Slack',            'https://slack.com',            '💬', 'Général'),
    ('Salesforce',       'https://salesforce.com',       '🏆', 'Commercial'),
    ('JIRA',             'https://jira.atlassian.com',   '🔧', 'IT'),
    ('Sage Finance',     'https://sage.com',             '💰', 'Finance'),
    ('Module RH',        'https://rh.internal',          '👥', 'RH');

INSERT INTO users (username, password, role) VALUES
    ('admin',   'changeme', 'admin'),
    ('manager', 'changeme', 'manager'),
    ('collab',  'changeme', 'collab');

INSERT INTO permissions (app_id, role) VALUES
    (1,'admin'),(1,'manager'),(1,'collab'),
    (2,'admin'),(2,'manager'),(2,'collab'),
    (3,'admin'),(3,'manager'),
    (4,'admin'),(4,'manager'),(4,'collab'),
    (5,'admin'),(5,'manager'),
    (6,'admin'),(6,'manager');