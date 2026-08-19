import os
import subprocess
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]


def compose(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )


def wait_ready(url: str, timeout: float = 900) -> float:
    started = monotonic()
    while monotonic() - started < timeout:
        try:
            if httpx.get(f"{url}/api/v1/health/live", timeout=2).status_code == 200:
                return monotonic() - started
        except httpx.HTTPError:
            pass
        sleep(1)
    raise AssertionError("web did not become ready")


def main_flow(url: str) -> tuple[str, str, str]:
    base = f"{url}/api/v1"
    with httpx.Client(base_url=base, timeout=70) as client:
        username = f"compose-{uuid4().hex[:12]}"
        password = "Senha local segura 2026!"
        assert (
            client.post(
                "/auth/register", json={"username": username, "password": password}
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/auth/register",
                json={"username": f" {username.upper()} ", "password": password},
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/auth/login",
                json={"username": username, "password": "senha incorreta"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/auth/login", json={"username": username, "password": password}
            ).status_code
            == 204
        )
        headers = {
            "X-CSRF-Token": client.cookies["notes_csrf"],
            "Origin": os.getenv("NOTES_TEST_ORIGIN", url),
        }
        note = client.post(
            "/notes",
            headers=headers,
            json={
                "title": "Project release",
                "content": "The software release is Friday at 2 PM.",
            },
        ).json()
        assert (
            client.post(
                "/notes",
                json={"title": "Sem CSRF", "content": "Deve falhar"},
            ).status_code
            == 403
        )
        deadline = monotonic() + 30
        while monotonic() < deadline:
            current = client.get(f"/notes/{note['id']}").json()
            if current["semantic_status"] == "ready":
                break
            sleep(0.5)
        assert current["semantic_status"] == "ready"
        assert (
            client.patch(
                f"/notes/{note['id']}",
                headers=headers | {"If-Match": '"1"'},
                json={"content": "The software release remains Friday at 2 PM."},
            ).status_code
            == 200
        )
        assert (
            client.patch(
                f"/notes/{note['id']}",
                headers=headers | {"If-Match": '"1"'},
                json={"content": "Stale write"},
            ).status_code
            == 409
        )
        deadline = monotonic() + 30
        while monotonic() < deadline:
            current = client.get(f"/notes/{note['id']}").json()
            if current["semantic_status"] == "ready":
                break
            sleep(0.5)
        assert current["semantic_status"] == "ready" and current["version"] == 2
        search = client.post(
            "/search/semantic",
            headers=headers,
            json={"query": "software release Friday 2 PM"},
        )
        assert search.status_code == 200 and search.json()["results"]
        chat = client.post(
            "/chat/messages",
            headers=headers,
            json={"message": "What day and time is the software release?"},
        )
        assert chat.status_code == 200 and chat.json()["sources"]

        disposable = client.post(
            "/notes",
            headers=headers,
            json={"title": "Disposable", "content": "Delete permanently."},
        ).json()
        assert client.delete(f"/notes/{disposable['id']}", headers=headers).status_code == 204
        assert client.get(f"/notes/{disposable['id']}").status_code == 404

        creation = client.post(
            "/chat/messages",
            headers=headers,
            json={
                "message": ("Crie uma anotação com título Compras e conteúdo Comprar café e arroz.")
            },
        )
        assert creation.status_code == 200
        assert creation.json()["intent"] == "create_note"
        assert creation.json()["created_note"] is not None

        with httpx.Client(base_url=base, timeout=70) as bob:
            bob_name = f"bob-{uuid4().hex[:12]}"
            assert (
                bob.post(
                    "/auth/register", json={"username": bob_name, "password": password}
                ).status_code
                == 201
            )
            assert (
                bob.post(
                    "/auth/login", json={"username": bob_name, "password": password}
                ).status_code
                == 204
            )
            bob_headers = {
                "X-CSRF-Token": bob.cookies["notes_csrf"],
                "Origin": os.getenv("NOTES_TEST_ORIGIN", url),
            }
            trap = bob.post(
                "/notes",
                headers=bob_headers,
                json={
                    "title": "Private trap",
                    "content": "The release is Friday at 2 PM. BOB-ONLY-TRAP.",
                },
            ).json()
            assert client.get(f"/notes/{trap['id']}").status_code == 404
            assert (
                client.patch(
                    f"/notes/{trap['id']}",
                    headers=headers | {"If-Match": '"1"'},
                    json={"content": "cross owner"},
                ).status_code
                == 404
            )
            assert client.delete(f"/notes/{trap['id']}", headers=headers).status_code == 404
            isolated = client.post(
                "/search/semantic",
                headers=headers,
                json={"query": "software release Friday 2 PM"},
            )
            assert isolated.status_code == 200
            assert trap["id"] not in {item["note_id"] for item in isolated.json()["results"]}

        assert client.post("/auth/logout", headers=headers).status_code == 204
        assert client.get("/auth/me").status_code == 401
        return username, password, note["id"]


def verify_persisted(url: str, credentials: tuple[str, str, str]) -> None:
    username, password, note_id = credentials
    with httpx.Client(base_url=f"{url}/api/v1", timeout=20) as client:
        assert (
            client.post(
                "/auth/login", json={"username": username, "password": password}
            ).status_code
            == 204
        )
        assert client.get(f"/notes/{note_id}").status_code == 200


@pytest.mark.e2e
@pytest.mark.compose
def test_build_migrate_model_init_main_flow_restart_and_shutdown_three_times() -> None:
    if os.getenv("NOTES_RUN_COMPOSE_ACCEPTANCE") != "1":
        pytest.skip("set NOTES_RUN_COMPOSE_ACCEPTANCE=1 on the host")
    url = os.getenv("NOTES_COMPOSE_URL", "http://localhost:8000")
    durations = []
    compose("build")
    for _run in range(3):
        compose("down", "--remove-orphans")
        subprocess.run(
            ["docker", "volume", "rm", "personal-notes-rag_postgres-data"],
            check=False,
            capture_output=True,
            text=True,
        )
        compose("up", "-d")
        durations.append(wait_ready(url, timeout=900))
        credentials = main_flow(url)
        compose("restart", "web", "index-worker", "db")
        wait_ready(url)
        verify_persisted(url, credentials)
    assert all(duration <= 900 for duration in durations)
    print(f"startup_durations_seconds={durations}")
    compose("down", "--remove-orphans")
