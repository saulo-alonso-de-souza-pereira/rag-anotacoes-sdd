from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from notes_rag.domain.notes import Note


class NoteNotFound(ValueError):
    pass


class VersionConflict(ValueError):
    pass


class NoteStore(Protocol):
    async def add(self, note: Note) -> None: ...
    async def get(self, note_id: UUID) -> Note | None: ...
    async def list(
        self, *, limit: int, before: tuple[datetime, UUID] | None = None
    ) -> list[Note]: ...
    async def save(self, note: Note, *, expected_version: int) -> bool: ...
    async def delete(self, note_id: UUID) -> bool: ...


class NoteService:
    def __init__(self, store: NoteStore, user_id: UUID, clock: Callable[[], datetime]) -> None:
        self.store, self.user_id, self.clock = store, user_id, clock

    async def create(self, title: str, content: str) -> Note:
        note = Note.create(uuid4(), self.user_id, title, content, self.clock())
        await self.store.add(note)
        return note

    async def get(self, note_id: UUID) -> Note:
        note = await self.store.get(note_id)
        if not note:
            raise NoteNotFound("note_not_found")
        return note

    async def update(
        self, note_id: UUID, *, title: str | None, content: str | None, expected_version: int
    ) -> Note:
        current = await self.get(note_id)
        updated = current.update(
            title=title,
            content=content,
            expected_version=expected_version,
            now=self.clock(),
        )
        if not await self.store.save(updated, expected_version=expected_version):
            raise VersionConflict("version_conflict")
        return updated

    async def delete(self, note_id: UUID) -> None:
        if not await self.store.delete(note_id):
            raise NoteNotFound("note_not_found")
