from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app.db import connect, initialize
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTES_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("NOTES_DEMO", "true")
    monkeypatch.delenv("NOTES_PASSWORD_1", raising=False)
    monkeypatch.delenv("NOTES_PASSWORD_2", raising=False)
    monkeypatch.delenv("NOTES_SECURE_COOKIE", raising=False)
    with TestClient(app) as test_client:
        yield test_client


def login(client, user=1):
    return client.post("/api/login", json={"username": f"demo{user}", "password": f"notas-demo-{user}"})


def create_note(client):
    folder_id = client.get("/api/folders").json()[0]["id"]
    response = client.post("/api/notes", json={"folder_id": folder_id, "title": "Lab OCI", "items": ["Crear VM"]})
    assert response.status_code == 201
    return response.json()


def test_login_creates_session_and_logout_invalidates_it(client):
    response = login(client)
    token = client.cookies.get("notes_session")
    assert response.json() == {"username": "demo1"}
    assert token and "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/me").status_code == 200
    with closing(connect()) as db:
        assert db.execute("SELECT token_hash FROM sessions").fetchone()[0] != token
    assert client.post("/api/logout").status_code == 204
    assert client.get("/api/me", headers={"Cookie": f"notes_session={token}"}).status_code == 401


def test_bad_password_does_not_create_a_session(client):
    response = client.post("/api/login", json={"username": "demo1", "password": "incorrecta"})
    assert response.status_code == 401
    assert client.cookies.get("notes_session") is None
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_create_note_persists_in_folder_after_reinitializing(client):
    assert login(client).status_code == 200
    note = create_note(client)
    initialize()
    assert client.get("/api/notes").json() == [note]
    assert note["items"][0]["label"] == "Crear VM"
    assert note["progress"] == {"completed": 0, "total": 1}


def test_mark_task_updates_progress_and_sqlite(client):
    login(client)
    note = create_note(client)
    item_id = note["items"][0]["id"]
    response = client.patch(f"/api/notes/{note['id']}/items/{item_id}", json={"done": True})
    assert response.json()["progress"] == {"completed": 1, "total": 1}
    assert client.get("/api/notes").json()[0]["items"][0]["done"] is True


def test_second_account_cannot_read_or_edit_first_accounts_notes(client):
    login(client)
    note = create_note(client)
    login(client, user=2)
    assert client.get("/api/notes").json() == []
    payload = {"folder_id": note["folder_id"], "title": "Nota de otra cuenta"}
    assert client.put(f"/api/notes/{note['id']}", json=payload).status_code == 404
    assert client.post("/api/notes", json=payload).status_code == 404


def test_deleting_note_cascades_to_its_checklist(client):
    login(client)
    note = create_note(client)
    assert client.delete(f"/api/notes/{note['id']}").status_code == 204
    assert client.get("/api/notes").json() == []
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM checklist_items WHERE note_id = ?", (note["id"],)).fetchone()[0] == 0
