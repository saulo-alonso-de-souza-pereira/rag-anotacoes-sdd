import json

import pytest

from notes_rag.domain.chat import ClassificationError
from notes_rag.services.intent import OLLAMA_INTENT_SCHEMA, IntentService


class SpyModel:
    def __init__(self, replies: list[str]) -> None:
        self.replies = iter(replies)
        self.prompts: list[str] = []

    async def complete(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        assert kwargs["temperature"] == 0
        assert kwargs["json_schema"]["additionalProperties"] is False
        return next(self.replies)


def encoded(intent: str, **fields: object) -> str:
    return json.dumps({"intent": intent, **fields})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "returned_intent"),
    [
        ("Segundo minhas notas, o que é Docker?", "general_chat"),
        ("O que é Docker?", "rag"),
        ("Crie uma nota sobre Docker", "clarification"),
        ("Docker nas minhas notas ou em geral?", "general_chat"),
    ],
)
async def test_message_shape_cannot_bypass_or_override_primary_model(
    message: str, returned_intent: str
) -> None:
    fields = {"needs_clarification": True} if returned_intent == "clarification" else {}
    model = SpyModel([encoded(returned_intent, **fields)])
    decision = await IntentService(model).classify(message)
    assert decision.intent == returned_intent
    assert len(model.prompts) == 1
    assert f"<mensagem>{message}</mensagem>" in model.prompts[0]


@pytest.mark.asyncio
async def test_complete_creation_is_decided_by_primary_model() -> None:
    model = SpyModel(
        [encoded("create_note", title="Compra", content="Leite", needs_clarification=False)]
    )
    decision = await IntentService(model).classify("Qual é a capital do Peru?")
    assert decision.complete_creation()
    assert len(model.prompts) == 1


@pytest.mark.asyncio
async def test_incomplete_creation_uses_one_same_model_repair() -> None:
    model = SpyModel(
        [
            encoded("create_note", needs_clarification=True),
            encoded(
                "create_note",
                title="Mercado",
                content="Comprar café",
                needs_clarification=False,
            ),
        ]
    )
    decision = await IntentService(model).classify("Crie uma nota chamada Mercado")
    assert decision.complete_creation()
    assert len(model.prompts) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "replies",
    [
        ["not-json", "still-not-json"],
        [encoded("tool_call"), encoded("tool_call")],
        [encoded("rag", owner_id="attacker"), encoded("rag", owner_id="attacker")],
    ],
)
async def test_invalid_classifier_output_fails_after_one_repair(replies: list[str]) -> None:
    model = SpyModel(replies)
    with pytest.raises(ClassificationError, match="classifier_output_invalid"):
        await IntentService(model).classify("O que é Docker?")
    assert len(model.prompts) == 2


@pytest.mark.asyncio
async def test_valid_clarification_is_not_a_classification_failure() -> None:
    model = SpyModel([encoded("clarification", title=None, content=None, needs_clarification=True)])
    decision = await IntentService(model).classify("Crie uma nota e explique Docker")
    assert decision.intent == "clarification"
    assert decision.needs_clarification
    assert len(model.prompts) == 1
    assert "mais de um resultado incompativel" in model.prompts[0]
    assert "'Crie uma nota e explique Docker' exige clarification" in model.prompts[0]
    assert "Crie uma nota chamada Docker com conteudo Estudar Docker." in model.prompts[0]
    assert "Crie uma nota e diga o que eu anotei sobre Docker." in model.prompts[0]
    assert "Mensagem: Explique Docker." in model.prompts[0]
    assert "Mensagem: O que eu anotei sobre Docker?" in model.prompts[0]


def test_ollama_schema_uses_grammar_compatible_keywords() -> None:
    intent = OLLAMA_INTENT_SCHEMA["properties"]["intent"]
    assert intent["enum"] == ["rag", "general_chat", "create_note", "clarification"]
    assert "pattern" not in intent
    assert "default" not in json.dumps(OLLAMA_INTENT_SCHEMA)
    assert set(OLLAMA_INTENT_SCHEMA["required"]) == {
        "intent",
        "title",
        "content",
        "needs_clarification",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "O que eu anotei sobre as decisões tomadas pelo time?",
        "O que eu anotei sobre a reunião secreta?",
    ],
)
async def test_note_questions_repair_invalid_fields_without_becoming_creation(
    message: str,
) -> None:
    model = SpyModel(
        [
            encoded(
                "rag",
                title=message,
                content="campo indevido",
                needs_clarification=False,
            ),
            encoded("rag", title=None, content=None, needs_clarification=False),
        ]
    )
    decision = await IntentService(model).classify(message)
    assert decision.intent == "rag"
    assert not decision.complete_creation()
    assert len(model.prompts) == 2
    assert message in model.prompts[1]
