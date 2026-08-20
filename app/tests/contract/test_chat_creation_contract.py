from pathlib import Path

import yaml

DOCUMENT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3] / "specs/001-personal-notes-rag/contracts/openapi.yaml"
    ).read_text(encoding="utf-8")
)


def test_chat_response_has_creation_and_clarification_discriminators() -> None:
    schema = DOCUMENT["components"]["schemas"]["ChatResponse"]
    properties = schema["properties"]
    assert properties["intent"]["enum"] == [
        "rag",
        "general_chat",
        "create_note",
        "clarification",
    ]
    assert properties["needs_clarification"]["type"] == "boolean"
    assert {item.get("$ref") for item in properties["created_note"]["oneOf"]} == {
        "#/components/schemas/Note",
        None,
    }
