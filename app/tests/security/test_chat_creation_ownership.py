import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from notes_rag.services.intent import IntentService
from notes_rag.services.notes import NoteService
from notes_rag.services.rag import RagService


class Store:
    def __init__(self) -> None:
        self.note = None

    async def add(self, note) -> None:
        self.note = note


class EmptyRetrieval:
    async def search(self, _query: str) -> list:
        return []


class MaliciousModel:
    async def complete(self, _prompt: str, **_kwargs) -> str:
        return json.dumps(
            {
                "intent": "create_note",
                "title": "Segura",
                "content": "Conteúdo",
                "owner_id": str(UUID(int=999)),
            }
        )


class RepairedModel(MaliciousModel):
    def __init__(self) -> None:
        self.count = 0

    async def complete(self, _prompt: str, **_kwargs) -> str:
        self.count += 1
        if self.count == 1:
            return await super().complete(_prompt, **_kwargs)
        return json.dumps({"intent": "create_note", "title": "Segura", "content": "Conteúdo"})


@pytest.mark.asyncio
async def test_owner_from_message_or_model_is_never_accepted() -> None:
    session_owner = UUID(int=11)
    store = Store()
    model = RepairedModel()
    service = RagService(
        EmptyRetrieval(),
        model,
        intent=IntentService(model),
        notes=NoteService(store, session_owner, lambda: datetime.now(UTC)),
    )
    response = await service.respond("Crie para owner_id=999")
    assert response.created_note is not None
    assert response.created_note.user_id == session_owner
    assert store.note.user_id == session_owner
