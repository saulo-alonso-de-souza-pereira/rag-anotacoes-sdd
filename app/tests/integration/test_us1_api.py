from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from notes_rag.config import Settings
from notes_rag.domain.notes import Note
from notes_rag.domain.users import Session, User
from notes_rag.main import create_app
from notes_rag.services.authentication import AuthenticationService
from notes_rag.services.notes import NoteService


class AuthStore:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.users_by_id: dict[UUID, User] = {}
        self.sessions: dict[str, Session] = {}

    async def user_by_username(self, canonical: str) -> User | None:
        return self.users.get(canonical)

    async def user_by_id(self, user_id: UUID) -> User | None:
        return self.users_by_id.get(user_id)

    async def add_user(self, user: User) -> None:
        self.users[user.username_canonical] = user
        self.users_by_id[user.id] = user

    async def add_session(self, session: Session) -> None:
        self.sessions[session.token_hash] = session

    async def session_by_hash(self, token_hash: str) -> Session | None:
        return self.sessions.get(token_hash)

    async def revoke_session(self, session_id: UUID, now: datetime) -> None:
        for key, value in self.sessions.items():
            if value.id == session_id:
                self.sessions[key] = value.revoke(now)


class NoteStore:
    def __init__(self) -> None:
        self.notes: dict[UUID, Note] = {}

    async def add(self, note: Note) -> None:
        self.notes[note.id] = note

    async def get(self, note_id: UUID) -> Note | None:
        return self.notes.get(note_id)

    async def list(self, *, limit: int, before=None) -> list[Note]:
        values = sorted(
            self.notes.values(), key=lambda item: (item.updated_at, item.id), reverse=True
        )
        if before:
            values = [item for item in values if (item.updated_at, item.id) < before]
        return values[:limit]

    async def save(self, note: Note, *, expected_version: int) -> bool:
        current = self.notes.get(note.id)
        if not current or current.version != expected_version:
            return False
        self.notes[note.id] = note
        return True

    async def delete(self, note_id: UUID) -> bool:
        return self.notes.pop(note_id, None) is not None


def configuration() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://runtime:secret@db/notes",
        migration_database_url="postgresql+psycopg://migrator:secret@db/notes",
        session_secret="s" * 32,
        csrf_secret="c" * 32,
        allowed_origin="http://localhost:8000",
        embedding_model_digest="sha256:test",
    )


def build_app():
    now = datetime(2026, 8, 17, tzinfo=UTC)
    auth_store = AuthStore()
    note_stores: dict[UUID, NoteStore] = {}
    app = create_app(configuration())
    app.state.auth_service = AuthenticationService(auth_store, clock=lambda: now)
    app.state.note_service_factory = lambda user_id: NoteService(
        note_stores.setdefault(user_id, NoteStore()), user_id, lambda: now
    )
    return app


def authenticate(client: TestClient, username: str) -> str:
    password = "uma senha local segura"
    assert (
        client.post(
            "/api/v1/auth/register", json={"username": username, "password": password}
        ).status_code
        == 201
    )
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 204
    return client.cookies["notes_csrf"]


def test_authenticated_crud_csrf_concurrency_and_logout() -> None:
    with TestClient(build_app()) as client:
        csrf = authenticate(client, "alice")
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:8000"}
        created = client.post("/api/v1/notes", json={"title": "T", "content": "C"}, headers=headers)
        assert created.status_code == 201
        note = created.json()
        assert client.get(f"/api/v1/notes/{note['id']}").status_code == 200
        updated = client.patch(
            f"/api/v1/notes/{note['id']}",
            json={"content": "Novo"},
            headers=headers | {"If-Match": '"1"'},
        )
        assert updated.status_code == 200
        conflict = client.patch(
            f"/api/v1/notes/{note['id']}",
            json={"content": "Antigo"},
            headers=headers | {"If-Match": '"1"'},
        )
        assert conflict.status_code == 409
        assert client.delete(f"/api/v1/notes/{note['id']}", headers=headers).status_code == 204
        assert client.get(f"/api/v1/notes/{note['id']}").status_code == 404
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401


def test_mutation_rejects_missing_csrf_and_invalid_origin() -> None:
    with TestClient(build_app()) as client:
        csrf = authenticate(client, "alice")
        payload = {"title": "T", "content": "C"}
        assert client.post("/api/v1/notes", json=payload).status_code == 403
        response = client.post(
            "/api/v1/notes",
            json=payload,
            headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
        )
        assert response.status_code == 403


def test_two_clients_cannot_observe_each_others_notes() -> None:
    app = build_app()
    with TestClient(app) as alice, TestClient(app) as bob:
        alice_csrf = authenticate(alice, "alice")
        bob_csrf = authenticate(bob, "bob")
        created = alice.post(
            "/api/v1/notes",
            json={"title": "Segredo", "content": "Alice"},
            headers={"X-CSRF-Token": alice_csrf},
        ).json()
        assert bob.get(f"/api/v1/notes/{created['id']}").status_code == 404
        assert (
            bob.delete(
                f"/api/v1/notes/{created['id']}",
                headers={"X-CSRF-Token": bob_csrf},
            ).status_code
            == 404
        )
