import os
from concurrent.futures import ThreadPoolExecutor
from statistics import quantiles
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest


def p95(values: list[float]) -> float:
    return quantiles(values, n=100, method="inclusive")[94]


def authenticated_client(base_url: str) -> httpx.Client:
    client = httpx.Client(base_url=base_url, timeout=70)
    username = f"perf-{uuid4().hex[:12]}"
    password = "Senha local segura 2026!"
    assert (
        client.post("/auth/register", json={"username": username, "password": password}).status_code
        == 201
    )
    assert (
        client.post("/auth/login", json={"username": username, "password": password}).status_code
        == 204
    )
    client.headers.update(
        {
            "X-CSRF-Token": client.cookies["notes_csrf"],
            "Origin": base_url.removesuffix("/api/v1"),
        }
    )
    return client


def elapsed(operation) -> tuple[float, httpx.Response]:
    started = monotonic()
    response = operation()
    return monotonic() - started, response


@pytest.mark.performance
@pytest.mark.live_model
def test_real_cpu_latency_targets_and_ten_active_sessions() -> None:
    base_url = os.getenv("NOTES_ACCEPTANCE_URL")
    if not base_url:
        pytest.skip("NOTES_ACCEPTANCE_URL is required for real Compose performance tests")
    clients = [authenticated_client(base_url) for _index in range(10)]
    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            created = list(
                executor.map(
                    lambda pair: elapsed(
                        lambda: pair[1].post(
                            "/notes",
                            json={
                                "title": f"Release {pair[0]}",
                                "content": "The software release is Friday at 2 PM.",
                            },
                        )
                    ),
                    enumerate(clients),
                )
            )
        assert all(response.status_code == 201 for _duration, response in created)
        assert p95([duration for duration, _response in created]) < 0.5

        deadline = monotonic() + 30
        note_ids = [response.json()["id"] for _duration, response in created]
        while monotonic() < deadline:
            statuses = [
                client.get(f"/notes/{note_id}").json()["semantic_status"]
                for client, note_id in zip(clients, note_ids, strict=True)
            ]
            if all(status == "ready" for status in statuses):
                break
            sleep(0.5)
        assert all(status == "ready" for status in statuses)

        with ThreadPoolExecutor(max_workers=10) as executor:
            searched = list(
                executor.map(
                    lambda client: elapsed(
                        lambda: client.post(
                            "/search/semantic",
                            json={"query": "software release Friday 2 PM"},
                        )
                    ),
                    clients,
                )
            )
        assert all(response.status_code == 200 for _duration, response in searched)
        assert p95([duration for duration, _response in searched]) < 2

        warmup_deadline = monotonic() + 180
        while True:
            warmup = clients[0].post(
                "/chat/messages",
                json={"message": "What day and time is the software release?"},
            )
            if warmup.status_code == 200:
                break
            assert warmup.status_code == 503 and monotonic() < warmup_deadline
            sleep(2)

        chat_durations = []
        for client in clients:
            duration, response = elapsed(
                lambda current=client: current.post(
                    "/chat/messages",
                    json={"message": "What day and time is the software release?"},
                )
            )
            assert response.status_code == 200
            assert response.json()["sources"]
            chat_durations.append(duration)
        assert sum(duration <= 60 for duration in chat_durations) / len(chat_durations) >= 0.9
    finally:
        for client in clients:
            client.close()
