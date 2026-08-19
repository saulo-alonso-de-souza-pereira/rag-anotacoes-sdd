from pathlib import Path

import yaml

DOCUMENT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3] / "specs/001-personal-notes-rag/contracts/openapi.yaml"
    ).read_text(encoding="utf-8")
)


def test_chat_contract_covers_grounded_insufficient_and_unavailable_outcomes() -> None:
    operation = DOCUMENT["paths"]["/chat/messages"]["post"]
    assert set(operation["responses"]) == {"200", "401", "403", "422", "503"}
    response = DOCUMENT["components"]["schemas"]["ChatResponse"]
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
