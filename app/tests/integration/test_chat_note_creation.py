import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from notes_rag.domain.notes import Note
from notes_rag.services.intent import IntentService
from notes_rag.services.notes import NoteService
from notes_rag.services.rag import RagService


class Store:
    def __init__(self) -> None:
        self.notes: dict[UUID, Note] = {}

    async def add(self, note: Note) -> None:
        self.notes[note.id] = note


class NoResults:
    async def search(self, _query: str) -> list:
        return []


class SequenceModel:
    def __init__(self, replies: list[dict]) -> None:
        self.replies = iter(replies)

    async def complete(self, _prompt: str, **_kwargs) -> str:
        return json.dumps(next(self.replies))


@pytest.mark.asyncio
async def test_clear_request_creates_exactly_one_persistent_note() -> None:
    owner = UUID(int=7)
    store = Store()
    model = SequenceModel(
        [{"intent": "create_note", "title": "Mercado", "content": "Comprar café"}]
    )
    notes = NoteService(store, owner, lambda: datetime.now(UTC))
    service = RagService(NoResults(), model, intent=IntentService(model), notes=notes)
    response = await service.respond("Crie uma nota para comprar café")
    assert response.created_note is not None
    assert response.created_note.user_id == owner
    assert list(store.notes) == [response.created_note.id]


@pytest.mark.asyncio
async def test_question_and_ambiguous_creation_write_nothing() -> None:
    owner = UUID(int=8)
    store = Store()
    model = SequenceModel(
        [
            {"intent": "rag"},
            {"intent": "create_note", "needs_clarification": True},
            {"intent": "create_note", "needs_clarification": True},
        ]
    )
    service = RagService(
        NoResults(),
        model,
        intent=IntentService(model),
        notes=NoteService(store, owner, lambda: datetime.now(UTC)),
    )
    assert (await service.respond("O que anotei?")).created_note is None
    clarification = await service.respond("Anote isso")
    assert clarification.needs_clarification
    assert not store.notes
