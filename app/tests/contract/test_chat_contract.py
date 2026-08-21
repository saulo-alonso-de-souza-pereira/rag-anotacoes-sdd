from pathlib import Path

import pytest
import yaml

from notes_rag.api.chat import ChatRequest, send_message
from notes_rag.api.errors import ApiError
from notes_rag.domain.chat import ClassificationError

DOCUMENT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3] / "specs/001-personal-notes-rag/contracts/openapi.yaml"
    ).read_text(encoding="utf-8")
)


def test_chat_contract_covers_grounded_insufficient_and_unavailable_outcomes() -> None:
    operation = DOCUMENT["paths"]["/chat/messages"]["post"]
    assert set(operation["responses"]) == {"200", "401", "403", "422", "502", "503"}
    assert operation["responses"]["502"]["$ref"].endswith("/ClassificationFailed")
    response = DOCUMENT["components"]["schemas"]["ChatResponse"]
    assert response["properties"]["intent"]["enum"] == [
        "rag",
        "general_chat",
        "create_note",
        "clarification",
    ]
    assert response["additionalProperties"] is False
    assert set(response["required"]) == {
        "intent",
        "answer",
        "needs_clarification",
        "sources",
    }
    source = DOCUMENT["components"]["schemas"]["Source"]
    assert set(source["required"]) == {"note_id", "title", "excerpt"}
    assert source["properties"]["excerpt"]["maxLength"] == 500
    assert "empty for general_chat" in response["properties"]["sources"]["description"]


class FailingClassifierService:
    async def respond(self, _message: str):
        raise ClassificationError("classifier_output_invalid")


@pytest.mark.asyncio
async def test_classifier_failure_maps_to_actionable_error_not_clarification() -> None:
    with pytest.raises(ApiError) as captured:
        await send_message(ChatRequest(message="O que é Docker?"), FailingClassifierService())
    error = captured.value
    assert error.status_code == 502
    assert error.code == "classification_failed"
    assert "reformula" in error.message.lower()
