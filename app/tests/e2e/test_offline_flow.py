import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FILES = ["-f", "compose.yaml", "-f", "compose.offline.yaml"]


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *FILES, *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )


@pytest.mark.e2e
@pytest.mark.compose
def test_search_and_chat_work_on_internal_network_without_external_llm_api() -> None:
    if os.getenv("NOTES_RUN_OFFLINE_ACCEPTANCE") != "1":
        pytest.skip("set NOTES_RUN_OFFLINE_ACCEPTANCE=1 on the host")
    try:
        run("down", "--remove-orphans")
        run("build", "web")
        run("up", "-d")
        inspection = subprocess.run(
            ["docker", "network", "inspect", "personal-notes-rag_default"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert json.loads(inspection.stdout)[0]["Internal"] is True
        result = run(
            "run",
            "--rm",
            "--no-deps",
            "-e",
            "NOTES_STACK_URL=http://web:8000",
            "-e",
            "NOTES_TEST_ORIGIN=http://localhost:18080",
            "web",
            "pytest",
            "-q",
            "tests/e2e/test_running_stack_flow.py",
            "--no-cov",
        )
        assert "1 passed" in result.stdout
    finally:
        run("down", "--remove-orphans")
