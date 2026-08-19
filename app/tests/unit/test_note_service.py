from datetime import UTC, datetime
from uuid import UUID

import pytest

from notes_rag.domain.notes import Note
from notes_rag.services.notes import NoteNotFound, NoteService, VersionConflict


class MemoryNoteStore:
    def __init__(self) -> None:
        self.notes: dict[UUID, Note] = {}
        self.force_conflict = False

    async def add(self, note: Note) -> None:
        self.notes[note.id] = note

    async def get(self, note_id: UUID) -> Note | None:
        return self.notes.get(note_id)

    async def list(self, *, limit: int, before=None) -> list[Note]:
        return list(self.notes.values())[:limit]

    async def save(self, note: Note, *, expected_version: int) -> bool:
        if self.force_conflict:
            return False
        self.notes[note.id] = note
        return True

    async def delete(self, note_id: UUID) -> bool:
        return self.notes.pop(note_id, None) is not None


@pytest.mark.asyncio
async def test_note_service_crud_and_permanent_delete() -> None:
    store = MemoryNoteStore()
    service = NoteService(
        store,
        UUID(int=1),
        lambda: datetime(2026, 8, 17, tzinfo=UTC),
    )
    note = await service.create("Título", "Conteúdo")
    assert await service.get(note.id) == note
    updated = await service.update(
        note.id,
        title="Novo",
        content=None,
        expected_version=1,
    )
    assert updated.version == 2
    await service.delete(note.id)
    with pytest.raises(NoteNotFound):
        await service.get(note.id)


@pytest.mark.asyncio
async def test_note_service_reports_concurrent_update_and_missing_delete() -> None:
    store = MemoryNoteStore()
    service = NoteService(store, UUID(int=1), lambda: datetime.now(UTC))
    note = await service.create("Título", "Conteúdo")
    store.force_conflict = True
    with pytest.raises(VersionConflict):
        await service.update(note.id, title="Novo", content=None, expected_version=1)
    with pytest.raises(NoteNotFound):
        await service.delete(UUID(int=99))
