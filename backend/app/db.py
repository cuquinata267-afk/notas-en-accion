import os
import sqlite3
from contextlib import closing
from hashlib import scrypt
from hmac import compare_digest
from pathlib import Path
from secrets import token_bytes


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    UNIQUE (user_id, name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS checklist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
);
CREATE INDEX IF NOT EXISTS notes_folder ON notes(folder_id);
CREATE INDEX IF NOT EXISTS checklist_note ON checklist_items(note_id);
"""


def connect():
    connection = sqlite3.connect(os.getenv("NOTES_DB", "notes.db"), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def database():
    with closing(connect()) as connection:
        yield connection


def password_hash(password, salt=None):
    salt = token_bytes(16) if salt is None else salt
    digest = scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


def password_matches(password, encoded):
    salt, _ = encoded.split(":", 1)
    return compare_digest(password_hash(password, bytes.fromhex(salt)), encoded)


def initialize():
    Path(os.getenv("NOTES_DB", "notes.db")).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as connection, connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)
        connection.execute("BEGIN IMMEDIATE")
        demo = os.getenv("NOTES_DEMO") == "true"
        for index in (1, 2):
            password = os.getenv(f"NOTES_PASSWORD_{index}") or (f"notas-demo-{index}" if demo else "")
            if not password:
                continue
            username = f"demo{index}"
            user = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user is None:
                result = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash(password)),
                )
                connection.execute("INSERT INTO folders (user_id, name) VALUES (?, 'Personal')", (result.lastrowid,))
            elif not password_matches(password, user["password_hash"]):
                connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash(password), user["id"]))
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
