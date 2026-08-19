import json
from uuid import uuid4

import pytest

from notes_rag.services.rag import INSUFFICIENT, RagService
from notes_rag.services.retrieval import RetrievalResult


class Retrieval:
    def __init__(self, item: RetrievalResult) -> None:
        self.item = item

    async def search(self, _query: str) -> list[RetrievalResult]:
        return [self.item]


class OllamaFake:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests: list[str] = []

    async def complete(self, prompt: str, **_kwargs) -> str:
        self.requests.append(prompt)
        return json.dumps(self.payload)


@pytest.mark.asyncio
async def test_retrieval_prompt_response_and_source_reconstruction() -> None:
    item = RetrievalResult(uuid4(), "Consulta", "Reunião às 14 horas.", 0.92)
    model = OllamaFake(
        {
            "answer": "A reunião é às 14 horas.",
            "citation_ids": [str(item.note_id)],
            "insufficient": False,
        }
    )
    response = await RagService(Retrieval(item), model).respond("Que horas é a reunião?")
    assert response.answer == "A reunião é às 14 horas."
    assert [source.note_id for source in response.sources] == [item.note_id]
    assert item.excerpt in model.requests[0]


@pytest.mark.asyncio
async def test_invented_citation_is_rejected_after_generation() -> None:
    item = RetrievalResult(uuid4(), "Nota", "Conteúdo", 0.9)
    model = OllamaFake({"answer": "Algo", "citation_ids": [str(uuid4())], "insufficient": False})
    response = await RagService(Retrieval(item), model).respond("Pergunta")
    assert response.answer == INSUFFICIENT
    assert not response.sources
