import json

import pytest

from notes_rag.services.intent import (
    IntentService,
    extract_explicit_creation,
    looks_like_creation_request,
)


class SequenceModel:
    def __init__(self, replies: list[str]) -> None:
        self.replies = iter(replies)
        self.calls = 0

    async def complete(self, _prompt: str, **kwargs) -> str:
        self.calls += 1
        assert kwargs["temperature"] == 0
        assert kwargs["json_schema"]["additionalProperties"] is False
        return next(self.replies)


def test_creation_guard_routes_only_explicit_write_requests() -> None:
    assert looks_like_creation_request("Crie uma nota sobre o projeto")
    assert looks_like_creation_request("Anote comprar café")
    assert looks_like_creation_request("Save a note for tomorrow")
    assert not looks_like_creation_request("O que anotei sobre o projeto?")
    assert not looks_like_creation_request("Qual é o horário?")


@pytest.mark.asyncio
async def test_strict_creation_intent_is_parsed() -> None:
    model = SequenceModel(
        [json.dumps({"intent": "create_note", "title": "Compra", "content": "Leite"})]
    )
    decision = await IntentService(model).classify("Anote comprar leite")
    assert decision.complete_creation()
    assert model.calls == 1


@pytest.mark.asyncio
async def test_malformed_output_gets_one_repair_then_fails_closed() -> None:
    model = SequenceModel(["not-json", '{"intent":"tool_call","owner_id":"attacker"}'])
    decision = await IntentService(model).classify("Crie uma nota")
    assert decision.intent == "create_note"
    assert decision.needs_clarification
    assert not decision.complete_creation()
    assert model.calls == 2


@pytest.mark.asyncio
async def test_missing_creation_fields_requires_clarification() -> None:
    model = SequenceModel(
        [
            json.dumps({"intent": "create_note", "needs_clarification": True}),
            json.dumps({"intent": "create_note", "needs_clarification": True}),
        ]
    )
    decision = await IntentService(model).classify("Anote isso")
    assert not decision.complete_creation()
    assert model.calls == 2


@pytest.mark.asyncio
async def test_incomplete_clear_creation_uses_single_repair() -> None:
    model = SequenceModel(
        [
            json.dumps({"intent": "create_note", "needs_clarification": True}),
            json.dumps(
                {
                    "intent": "create_note",
                    "title": "Mercado",
                    "content": "Comprar café",
                    "needs_clarification": False,
                }
            ),
        ]
    )
    decision = await IntentService(model).classify(
        "Crie uma nota chamada Mercado com conteúdo Comprar café"
    )
    assert decision.complete_creation()
    assert model.calls == 2


@pytest.mark.parametrize(
    ("message", "title", "content"),
    [
        (
            "Crie uma anotação com título Compras e conteúdo Comprar café e arroz.",
            "Compras",
            "Comprar café e arroz.",
        ),
        (
            "Create a note titled Shopping with content coffee and rice.",
            "Shopping",
            "coffee and rice.",
        ),
    ],
)
def test_strict_explicit_creation_fallback(message: str, title: str, content: str) -> None:
    decision = extract_explicit_creation(message)
    assert decision is not None
    assert decision.title == title
    assert decision.content == content


def test_explicit_creation_fallback_rejects_missing_fields() -> None:
    assert extract_explicit_creation("Crie uma nota sobre compras") is None
