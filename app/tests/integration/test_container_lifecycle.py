from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_startup_order_migrations_restart_and_worker_recovery_are_declared() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["web"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["index-worker"]["depends_on"]["model-init"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["db"]["restart"] == "unless-stopped"
    assert services["ollama"]["restart"] == "unless-stopped"
    migration = (ROOT / "scripts/migrate.ps1").read_text(encoding="utf-8")
    assert migration.count("docker compose run --rm migrate") == 2
    worker = (ROOT / "app/src/notes_rag/worker.py").read_text(encoding="utf-8")
    assert "use_claim_function=True" in worker
