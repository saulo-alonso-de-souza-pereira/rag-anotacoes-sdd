from pathlib import Path

import yaml

DOCUMENT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3] / "specs/001-personal-notes-rag/contracts/openapi.yaml"
    ).read_text(encoding="utf-8")
)


def test_auth_operations_and_status_codes_are_stable() -> None:
    expected = {
        "/auth/register": {"post": {"201", "409", "422"}},
        "/auth/login": {"post": {"204", "401", "422", "429"}},
        "/auth/logout": {"post": {"204", "401", "403"}},
        "/auth/me": {"get": {"200", "401"}},
    }
    for path, operations in expected.items():
        for method, statuses in operations.items():
            assert set(DOCUMENT["paths"][path][method]["responses"]) == statuses


def test_credentials_are_write_only_and_ownership_is_not_accepted() -> None:
    schemas = DOCUMENT["components"]["schemas"]
    assert schemas["RegisterRequest"]["properties"]["password"]["writeOnly"] is True
    assert schemas["LoginRequest"]["properties"]["password"]["writeOnly"] is True
    assert "user_id" not in schemas["RegisterRequest"]["properties"]
    assert "user_id" not in schemas["LoginRequest"]["properties"]
