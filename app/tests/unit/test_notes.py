from datetime import UTC, datetime
from uuid import UUID

import pytest

from notes_rag.domain.notes import Note, SemanticStatus


def make_note() -> Note:
    now = datetime(2026, 8, 17, tzinfo=UTC)
    return Note.create(UUID(int=1), UUID(int=2), " Título ", " Conteúdo ", now)


def test_note_creation_normalizes_fields_and_starts_pending() -> None:
    note = make_note()
    assert note.title == "Título"
    assert note.content == "Conteúdo"
    assert note.version == 1
    assert note.semantic_status is SemanticStatus.PENDING


@pytest.mark.parametrize(("title", "content"), [("", "ok"), ("ok", ""), (" " * 2, "ok")])
def test_note_rejects_blank_fields(title: str, content: str) -> None:
    with pytest.raises(ValueError):
        Note.create(
            UUID(int=1),
            UUID(int=2),
            title,
            content,
            datetime.now(UTC),
        )


def test_update_increments_version_and_invalidates_semantic_state() -> None:
    note = make_note().mark_ready(datetime(2026, 8, 17, 12, 1, tzinfo=UTC))
    updated = note.update(
        title=None,
        content="Novo conteúdo",
        now=datetime(2026, 8, 17, 12, 2, tzinfo=UTC),
    )
    assert updated.version == 2
    assert updated.semantic_status is SemanticStatus.PENDING
    assert updated.semantic_error_code is None


def test_update_requires_current_version() -> None:
    with pytest.raises(ValueError, match="version_conflict"):
        make_note().update(
            title="Novo",
            content=None,
            now=datetime.now(UTC),
            expected_version=2,
        )
