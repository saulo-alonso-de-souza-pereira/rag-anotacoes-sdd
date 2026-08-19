from pathlib import Path

import yaml

DOCUMENT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3] / "specs/001-personal-notes-rag/contracts/openapi.yaml"
    ).read_text(encoding="utf-8")
)


def test_note_crud_contract_includes_pagination_and_optimistic_concurrency() -> None:
    paths = DOCUMENT["paths"]
    assert {"get", "post"} <= set(paths["/notes"])
    assert {"get", "patch", "delete"} <= set(paths["/notes/{noteId}"])
    patch_parameters = paths["/notes/{noteId}"]["patch"]["parameters"]
    assert {"$ref": "#/components/parameters/IfMatchVersion"} in patch_parameters
    list_parameters = paths["/notes"]["get"]["parameters"]
    assert {item["name"] for item in list_parameters} == {"cursor", "limit"}


def test_missing_and_cross_owner_notes_share_one_public_response() -> None:
    paths = DOCUMENT["paths"]["/notes/{noteId}"]
    for method in ("get", "patch", "delete"):
        assert paths[method]["responses"]["404"] == {"$ref": "#/components/responses/NoteNotFound"}


def test_note_payloads_never_accept_owner_or_semantic_state() -> None:
    schemas = DOCUMENT["components"]["schemas"]
    for name in ("NoteCreate", "NoteUpdate"):
        properties = schemas[name]["properties"]
        assert "user_id" not in properties
        assert "semantic_status" not in properties
