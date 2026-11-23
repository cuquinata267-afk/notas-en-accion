import os
import sqlite3
from contextlib import asynccontextmanager
from hashlib import sha256
from secrets import token_urlsafe
from time import time
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, StringConstraints

from .db import database, initialize, password_hash, password_matches

Db = Annotated[sqlite3.Connection, Depends(database)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
FolderName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
ItemLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
SessionCookie = Annotated[str | None, Cookie(alias="notes_session")]
SESSION_SECONDS = 7 * 24 * 60 * 60
DUMMY_PASSWORD_HASH = password_hash(token_urlsafe(16))


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class FolderInput(BaseModel):
    name: FolderName


class NoteInput(BaseModel):
    folder_id: int
    title: Title
    body: str = Field(default="", max_length=8000)


class NewNote(NoteInput):
    items: list[ItemLabel] = Field(default_factory=list, max_length=30)


class NewItem(BaseModel):
    label: ItemLabel


class CheckItem(BaseModel):
    done: bool


def token_hash(token):
    return sha256(token.encode()).hexdigest()


def current_user(db: Db, notes_session: SessionCookie = None):
    if notes_session:
        user = db.execute(
            """SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE token_hash = ? AND expires_at > ?""",
            (token_hash(notes_session), int(time())),
        ).fetchone()
        if user:
            return dict(user)
    raise HTTPException(401, "Inicia sesión para continuar.")


User = Annotated[dict, Depends(current_user)]


def progress(items):
    return {"completed": sum(item["done"] for item in items), "total": len(items)}


def as_note(db, note):
    items = [dict(id=item["id"], label=item["label"], done=bool(item["done"])) for item in db.execute(
        "SELECT id, label, done FROM checklist_items WHERE note_id = ? ORDER BY id", (note["id"],)
    )]
    return {**dict(note), "items": items, "progress": progress(items)}


def find_note(db, note_id, user_id):
    note = db.execute(
        "SELECT notes.* FROM notes JOIN folders ON folders.id = notes.folder_id WHERE notes.id = ? AND folders.user_id = ?",
        (note_id, user_id),
    ).fetchone()
    if not note:
        raise HTTPException(404, "Nota no encontrada.")
    return note


def require_folder(db, folder_id, user_id):
    if not db.execute("SELECT 1 FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id)).fetchone():
        raise HTTPException(404, "Carpeta no encontrada.")


@asynccontextmanager
async def lifespan(_app):
    initialize()
    yield


app = FastAPI(title="Notas en Acción", lifespan=lifespan)


@app.get("/api/health")
def health(db: Db):
    db.execute("SELECT 1 FROM notes LIMIT 1").fetchone()
    return {"status": "ok"}


@app.post("/api/login")
def login(data: Login, response: Response, db: Db):
    user = db.execute("SELECT * FROM users WHERE username = ?", (data.username.strip().lower(),)).fetchone()
    valid = password_matches(data.password, user["password_hash"] if user else DUMMY_PASSWORD_HASH)
    if not user or not valid:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    token = token_urlsafe(32)
    now = int(time())
    with db:
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        db.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash(token), user["id"], now + SESSION_SECONDS),
        )
    response.set_cookie("notes_session", token, max_age=SESSION_SECONDS, httponly=True,
                        samesite="strict", secure=os.getenv("NOTES_SECURE_COOKIE") == "true")
    response.headers["Cache-Control"] = "no-store"
    return {"username": user["username"]}


@app.get("/api/me")
def me(user: User):
    return {"username": user["username"]}


@app.post("/api/logout", status_code=204)
def logout(response: Response, db: Db, notes_session: SessionCookie = None):
    if notes_session:
        with db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(notes_session),))
    response.delete_cookie("notes_session", httponly=True, samesite="strict",
                           secure=os.getenv("NOTES_SECURE_COOKIE") == "true")


@app.get("/api/folders")
def list_folders(db: Db, user: User):
    return [dict(row) for row in db.execute(
        "SELECT id, name FROM folders WHERE user_id = ? ORDER BY name COLLATE NOCASE", (user["id"],)
    )]


@app.post("/api/folders", status_code=201)
def add_folder(data: FolderInput, db: Db, user: User):
    try:
        with db:
            result = db.execute("INSERT INTO folders (user_id, name) VALUES (?, ?)", (user["id"], data.name))
    except sqlite3.IntegrityError as error:
        raise HTTPException(409, "Ya tienes una carpeta con ese nombre.") from error
    return {"id": result.lastrowid, "name": data.name}


@app.get("/api/notes")
def list_notes(db: Db, user: User):
    rows = db.execute(
        """SELECT notes.* FROM notes JOIN folders ON folders.id = notes.folder_id
           WHERE folders.user_id = ? ORDER BY notes.updated_at DESC, notes.id DESC""", (user["id"],)
    )
    return [as_note(db, row) for row in rows]


@app.post("/api/notes", status_code=201)
def add_note(data: NewNote, db: Db, user: User):
    require_folder(db, data.folder_id, user["id"])
    with db:
        result = db.execute("INSERT INTO notes (folder_id, title, body) VALUES (?, ?, ?)",
                            (data.folder_id, data.title, data.body))
        note_id = result.lastrowid
        db.executemany("INSERT INTO checklist_items (note_id, label) VALUES (?, ?)",
                       [(note_id, label) for label in data.items])
        return as_note(db, find_note(db, note_id, user["id"]))


@app.put("/api/notes/{note_id}")
def edit_note(note_id: int, data: NoteInput, db: Db, user: User):
    find_note(db, note_id, user["id"])
    require_folder(db, data.folder_id, user["id"])
    with db:
        db.execute("UPDATE notes SET title = ?, body = ?, folder_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (data.title, data.body, data.folder_id, note_id))
        return as_note(db, find_note(db, note_id, user["id"]))


@app.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Db, user: User):
    find_note(db, note_id, user["id"])
    with db:
        db.execute("DELETE FROM notes WHERE id = ?", (note_id,))


@app.post("/api/notes/{note_id}/items", status_code=201)
def add_item(note_id: int, data: NewItem, db: Db, user: User):
    with db:
        db.execute("BEGIN IMMEDIATE")
        note = find_note(db, note_id, user["id"])
        count = db.execute("SELECT COUNT(*) FROM checklist_items WHERE note_id = ?", (note_id,)).fetchone()[0]
        if count >= 30:
            raise HTTPException(409, "La nota ya tiene 30 tareas.")
        db.execute("INSERT INTO checklist_items (note_id, label) VALUES (?, ?)", (note_id, data.label))
        return as_note(db, note)


@app.patch("/api/notes/{note_id}/items/{item_id}")
def update_item(note_id: int, item_id: int, data: CheckItem, db: Db, user: User):
    find_note(db, note_id, user["id"])
    with db:
        result = db.execute("UPDATE checklist_items SET done = ? WHERE id = ? AND note_id = ?",
                            (data.done, item_id, note_id))
        if not result.rowcount:
            raise HTTPException(404, "Tarea no encontrada.")
        return as_note(db, find_note(db, note_id, user["id"]))
