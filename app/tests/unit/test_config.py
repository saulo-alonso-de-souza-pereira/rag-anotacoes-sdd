import pytest
from pydantic import ValidationError

from notes_rag.config import Settings


def valid_environment() -> dict[str, str]:
    return {
        "database_url": "postgresql+psycopg://runtime:secret@db/notes",
        "migration_database_url": "postgresql+psycopg://migrator:secret@db/notes",
        "session_secret": "s" * 32,
        "csrf_secret": "c" * 32,
        "embedding_model_digest": "sha256:test",
    }


def test_settings_expose_safe_model_and_retrieval_defaults() -> None:
    settings = Settings(**valid_environment())
    assert settings.embedding_model == "embeddinggemma:300m"
    assert settings.generation_model == "llama3:latest"
    assert settings.generation_model_id == "365c0bd3c000"
    assert settings.retrieval_limit == 5
    assert settings.retrieval_minimum_similarity == 0.55


def test_settings_reject_placeholder_or_short_secrets() -> None:
    values = valid_environment() | {"session_secret": "CHANGE_ME"}
    with pytest.raises(ValidationError):
        Settings(**values)


def test_runtime_and_migration_database_roles_must_differ() -> None:
    values = valid_environment()
    values["migration_database_url"] = values["database_url"]
    with pytest.raises(ValidationError):
        Settings(**values)
