from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_images_services_healthchecks_and_named_volumes_are_explicit() -> None:
    services = COMPOSE["services"]
    assert set(services) == {"web", "index-worker", "db", "ollama", "migrate", "model-init"}
    assert services["db"]["image"] == "pgvector/pgvector:pg18"
    assert services["ollama"]["image"] == "ollama/ollama:0.30.6"
    assert "healthcheck" in services["db"] and "healthcheck" in services["ollama"]
    assert set(COMPOSE["volumes"]) == {"postgres-data", "ollama-models"}


def test_application_image_is_multistage_non_root_and_env_is_not_copied() -> None:
    assert DOCKERFILE.count("FROM ") == 2
    assert "USER notes" in DOCKERFILE
    assert "COPY .env" not in DOCKERFILE
    assert "HEALTHCHECK" in DOCKERFILE
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in dockerignore
