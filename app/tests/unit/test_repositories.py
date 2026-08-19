from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from notes_rag.domain.notes import Note
from notes_rag.domain.users import Session, User
from notes_rag.persistence.models import NoteRecord, SessionRecord, UserRecord
from notes_rag.persistence.repositories import NoteRepository, SessionRepository, UserRepository

NOW = datetime(2026, 8, 17, tzinfo=UTC)


class ScalarResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.scalar_values: list[object | None] = []
        self.list_values: list[object] = []
        self.get_value: object | None = None
        self.rowcount = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None

    async def scalar(self, _query: object) -> object | None:
        return self.scalar_values.pop(0)

    async def scalars(self, _query: object) -> ScalarResult:
        return ScalarResult(self.list_values)

    async def get(self, _model: object, _identifier: object) -> object | None:
        return self.get_value

    async def execute(self, _query: object) -> SimpleNamespace:
        return SimpleNamespace(rowcount=self.rowcount)


def user() -> User:
    return User.create(UUID(int=1), "Alice", "hash", NOW)


def session() -> Session:
    return Session(UUID(int=2), UUID(int=1), "token", "csrf", NOW, NOW, NOW)


def note() -> Note:
    return Note.create(UUID(int=3), UUID(int=1), "Título", "Conteúdo", NOW)


@pytest.mark.asyncio
async def test_user_and_session_repository_map_records() -> None:
    db = FakeSession()
    users = UserRepository(db)  # type: ignore[arg-type]
    sessions = SessionRepository(db)  # type: ignore[arg-type]
    await users.add(user())
    await sessions.add(session())
    assert isinstance(db.added[0], UserRecord)
    assert isinstance(db.added[1], SessionRecord)
    db.scalar_values = [db.added[0], db.added[1], None]
    assert await users.by_canonical_username("alice") == user()
    assert await sessions.by_token_hash("token") == session()
    assert await sessions.by_token_hash("missing") is None
    db.get_value = db.added[1]
    await sessions.revoke(UUID(int=2), NOW)
    assert db.added[1].revoked_at == NOW


@pytest.mark.asyncio
async def test_note_repository_is_owner_scoped_and_supports_cursor_crud() -> None:
    db = FakeSession()
    repository = NoteRepository(db, UUID(int=1))  # type: ignore[arg-type]
    value = note()
    await repository.add(value)
    record = db.added[0]
    assert isinstance(record, NoteRecord)
    db.scalar_values = [record, record]
    assert await repository.get(value.id) == value
    db.list_values = [record]
    assert await repository.list(limit=20, before=(NOW, UUID(int=4))) == [value]
    updated = value.update(title="Novo", content=None, now=NOW)
    assert await repository.save(updated, expected_version=1)
    assert record.version == 2
    db.rowcount = 1
    assert await repository.delete(value.id)


@pytest.mark.asyncio
async def test_note_repository_fails_closed_for_wrong_owner_and_conflict() -> None:
    db = FakeSession()
    repository = NoteRepository(db, UUID(int=9))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="owner_mismatch"):
        await repository.add(note())
    db.scalar_values = [None, None]
    assert await repository.get(UUID(int=3)) is None
    assert not await repository.save(note(), expected_version=1)
    db.rowcount = 0
    assert not await repository.delete(UUID(int=3))
