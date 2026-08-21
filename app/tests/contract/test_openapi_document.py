from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-personal-notes-rag"
    / "contracts"
    / "openapi.yaml"
)


def test_contract_is_openapi_31_with_cookie_security() -> None:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert document["openapi"].startswith("3.1.")
    scheme = document["components"]["securitySchemes"]["sessionCookie"]
    assert scheme == {
        "type": "apiKey",
        "in": "cookie",
        "name": "__Host-notes_session",
        "description": scheme["description"],
    }
    assert document["security"] == [{"sessionCookie": []}]


def test_schema_fragments_are_valid_json_schema_2020_12() -> None:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    for schema in document["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)


def test_public_mutations_require_csrf_header() -> None:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    for path, operation in (
        ("/notes", "post"),
        ("/notes/{noteId}", "patch"),
        ("/notes/{noteId}", "delete"),
        ("/chat/messages", "post"),
    ):
        parameters = document["paths"][path][operation].get("parameters", [])
        assert {"$ref": "#/components/parameters/CsrfToken"} in parameters


def test_semantic_retrieval_is_not_a_public_api() -> None:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert "/search/semantic" not in document["paths"]
    assert "Search" not in {tag["name"] for tag in document.get("tags", [])}
    assert "502" in document["paths"]["/chat/messages"]["post"]["responses"]
