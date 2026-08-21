import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from notes_rag.domain.chat import ClassificationError
from notes_rag.domain.notes import Note
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
    def __init__(self, replies, events=None):
        self.replies = iter(replies)
        self.events = events if events is not None else []

    async def complete(self, _prompt, **kwargs):
        is_classifier = "json_schema" in kwargs
        self.events.append("classify" if is_classifier else "generate")
        value = next(self.replies)
        return value if isinstance(value, str) else json.dumps(value)


class EventRetrieval(Retrieval):
    def __init__(self, results, events):
        super().__init__(results)
        self.events = events

    async def search(self, query):
        self.events.append("retrieve")
        return await super().search(query)


class Notes:
    def __init__(self, events):
        self.events = events

    async def create(self, title, content):
        self.events.append("create")
        now = datetime(2026, 8, 20, tzinfo=UTC)
        return Note.create(uuid4(), uuid4(), title, content, now)


@pytest.mark.asyncio
async def test_message_router_branch_and_response_with_related_note() -> None:
    note = RetrievalResult(uuid4(), "Docker", "Docker usa containers.", 0.95)
    retrieval = Retrieval([note])
    model = Model([{"intent": "general_chat"}, "Docker é uma plataforma."])
    response = await RagService(retrieval, model, intent=IntentService(model)).respond(
        "O que é Docker?"
    )
    assert response.intent == "general_chat" and response.sources == ()
    assert retrieval.calls == 0


@pytest.mark.asyncio
async def test_explicit_rag_without_results_stays_insufficient() -> None:
    retrieval = Retrieval([])
    model = Model([{"intent": "rag"}])
    response = await RagService(retrieval, model, intent=IntentService(model)).respond(
        "Segundo minhas notas, o que é Docker?"
    )
    assert response.intent == "rag" and response.answer == INSUFFICIENT
    assert retrieval.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("classifier", "expected_events"),
    [
        ({"intent": "general_chat"}, ["classify", "generate"]),
        ({"intent": "rag"}, ["classify", "retrieve"]),
        (
            {"intent": "create_note", "title": "T", "content": "C"},
            ["classify", "create"],
        ),
        (
            {"intent": "clarification", "needs_clarification": True},
            ["classify"],
        ),
    ],
)
async def test_validated_classification_precedes_selected_branch(
    classifier: dict, expected_events: list[str]
) -> None:
    events = []
    replies = [classifier]
    if classifier["intent"] == "general_chat":
        replies.append("Resposta geral")
    model = Model(replies, events)
    response = await RagService(
        EventRetrieval([], events),
        model,
        intent=IntentService(model),
        notes=Notes(events),
    ).respond("mensagem com qualquer formato")
    assert response.intent == classifier["intent"]
    assert events == expected_events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "classifier", "expected_events"),
    [
        (
            "Crie uma nota e explique Docker",
            {"intent": "clarification", "needs_clarification": True},
            ["classify"],
        ),
        (
            "Crie uma nota chamada Compras com o conteudo cafe e arroz.",
            {"intent": "create_note", "title": "Compras", "content": "cafe e arroz"},
            ["classify", "create"],
        ),
        (
            "O que eu anotei sobre Docker?",
            {"intent": "rag"},
            ["classify", "retrieve"],
        ),
        (
            "Qual e a capital do Peru?",
            {"intent": "general_chat"},
            ["classify", "generate"],
        ),
        (
            "Docker nas minhas notas ou em geral?",
            {"intent": "clarification", "needs_clarification": True},
            ["classify"],
        ),
    ],
)
async def test_intent_examples_execute_only_the_model_selected_branch(
    message: str,
    classifier: dict,
    expected_events: list[str],
) -> None:
    events = []
    replies = [classifier]
    if classifier["intent"] == "general_chat":
        replies.append("Resposta geral")
    model = Model(replies, events)

    response = await RagService(
        EventRetrieval([], events),
        model,
        intent=IntentService(model),
        notes=Notes(events),
    ).respond(message)

    assert response.intent == classifier["intent"]
    assert events == expected_events
    assert events.count("create") == (1 if classifier["intent"] == "create_note" else 0)


@pytest.mark.asyncio
async def test_invalid_classification_touches_no_branch() -> None:
    events = []
    model = Model(["invalid", "still-invalid"], events)
    with pytest.raises(ClassificationError):
        await RagService(
            EventRetrieval([], events),
            model,
            intent=IntentService(model),
            notes=Notes(events),
        ).respond("O que é Docker?")
    assert events == ["classify", "classify"]
