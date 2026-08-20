import json
from uuid import uuid4

import pytest

from notes_rag.services.intent import IntentService
from notes_rag.services.rag import INSUFFICIENT, RagService
from notes_rag.services.retrieval import RetrievalResult


class Retrieval:
    def __init__(self, results):
        self.results = results
        self.calls = 0

    async def search(self, _query):
        self.calls += 1
        return self.results


class Model:
    def __init__(self, replies):
        self.replies = iter(replies)

    async def complete(self, _prompt, **_kwargs):
        value = next(self.replies)
        return value if isinstance(value, str) else json.dumps(value)


@pytest.mark.asyncio
async def test_message_router_branch_and_response_with_related_note() -> None:
    note = RetrievalResult(uuid4(), "Docker", "Docker usa containers.", 0.95)
    retrieval = Retrieval([note])
    model = Model(["Docker é uma plataforma."])
    response = await RagService(retrieval, model, intent=IntentService(model)).respond(
        "O que é Docker?"
    )
    assert response.intent == "general_chat" and response.sources == ()
    assert retrieval.calls == 0


@pytest.mark.asyncio
async def test_explicit_rag_without_results_stays_insufficient() -> None:
    retrieval = Retrieval([])
    model = Model([])
    response = await RagService(retrieval, model, intent=IntentService(model)).respond(
        "Segundo minhas notas, o que é Docker?"
    )
    assert response.intent == "rag" and response.answer == INSUFFICIENT
    assert retrieval.calls == 1
