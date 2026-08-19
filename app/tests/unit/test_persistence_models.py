from uuid import UUID

import pytest

from notes_rag.persistence.models import (
    Base,
    IndexingJobRecord,
    NoteChunkRecord,
    NoteRecord,
    SessionRecord,
    UserRecord,
)
from notes_rag.persistence.rls import assert_current_user, set_current_user


def test_core_tables_define_ownership_and_uniqueness_constraints() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "sessions",
        "notes",
        "note_chunks",
        "indexing_jobs",
    }
    assert UserRecord.__table__.c.username_canonical.unique
    assert SessionRecord.__table__.c.token_hash.unique
    assert NoteRecord.__table__.c.user_id.nullable is False
    constraint_names = {item.name for item in NoteRecord.__table__.constraints}
    assert "uq_notes_id_user" in constraint_names
    assert NoteChunkRecord.__table__.c.embedding.type.dim == 768
    assert IndexingJobRecord.__table__.c.attempt_count.default.arg == 0


class FakeSession:
    def __init__(self, current: str | None = None) -> None:
        self.current = current
        self.execution: tuple[object, dict[str, str]] | None = None

    async def execute(self, statement: object, parameters: dict[str, str]) -> None:
        self.execution = (statement, parameters)

    async def scalar(self, _statement: object, _parameters: dict[str, str]) -> str | None:
        return self.current


@pytest.mark.asyncio
async def test_rls_context_is_transaction_local_and_asserted() -> None:
    user_id = UUID(int=1)
    session = FakeSession(str(user_id))
    await set_current_user(session, user_id)  # type: ignore[arg-type]
    assert session.execution is not None
    assert session.execution[1]["user_id"] == str(user_id)
    await assert_current_user(session, user_id)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rls_assertion_fails_closed_without_matching_context() -> None:
    with pytest.raises(RuntimeError, match="rls_context_missing"):
        await assert_current_user(FakeSession(), UUID(int=1))  # type: ignore[arg-type]
