from pathlib import Path

import yaml

DOCUMENT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3] / "specs/001-personal-notes-rag/contracts/openapi.yaml"
    ).read_text(encoding="utf-8")
)


def test_semantic_search_contract_limits_query_and_results() -> None:
    operation = DOCUMENT["paths"]["/search/semantic"]["post"]
    assert set(operation["responses"]) == {"200", "401", "403", "422", "503"}
    schema = DOCUMENT["components"]["schemas"]["SemanticSearchRequest"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["query"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 2000,
    }
    assert schema["properties"]["limit"]["maximum"] == 10
    assert (
        DOCUMENT["components"]["schemas"]["SemanticSearchResponse"]["properties"]["results"][
            "maxItems"
        ]
        == 10
    )


def test_retry_indexing_contract_requires_csrf_and_has_explicit_outcomes() -> None:
    operation = DOCUMENT["paths"]["/notes/{noteId}/retry-indexing"]["post"]
    assert {item.get("$ref") for item in operation["parameters"]} == {
        "#/components/parameters/NoteId",
        "#/components/parameters/CsrfToken",
    }
    assert set(operation["responses"]) == {"202", "401", "403", "404", "409"}
