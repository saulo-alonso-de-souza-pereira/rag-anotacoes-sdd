from fastapi.testclient import TestClient

from notes_rag.config import Settings
from notes_rag.main import create_app


def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://runtime:secret@db/notes",
        migration_database_url="postgresql+psycopg://migrator:secret@db/notes",
        session_secret="s" * 32,
        csrf_secret="c" * 32,
        embedding_model_digest="sha256:test",
    )


def test_application_serves_static_shell_and_liveness() -> None:
    with TestClient(create_app(settings())) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Anotações pessoais" in page.text
        response = client.get("/api/v1/health/live")
        assert response.json() == {"status": "ok"}
        assert response.headers["x-request-id"]


def test_readiness_fails_safely_when_dependency_is_unavailable() -> None:
    async def unavailable() -> bool:
        return False

    with TestClient(create_app(settings(), database_probe=unavailable)) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_ready"
        assert "postgres" not in response.text.casefold()
