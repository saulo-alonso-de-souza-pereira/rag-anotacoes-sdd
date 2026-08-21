import json
import os
from concurrent.futures import ThreadPoolExecutor
from statistics import quantiles
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest

from notes_rag.services.intent import IntentService
from notes_rag.services.rag import RagService
from notes_rag.services.retrieval import RetrievalResult


def p95(values: list[float]) -> float:
    return quantiles(values, n=100, method="inclusive")[94]


def authenticated_client(base_url: str) -> httpx.Client:
    normalized_base_url = base_url.rstrip("/") + "/"
    client = httpx.Client(base_url=normalized_base_url, timeout=70)
    username = f"perf-{uuid4().hex[:12]}"
    password = "Senha local segura 2026!"
    assert (
        client.post("auth/register", json={"username": username, "password": password}).status_code
        == 201
    )
    assert (
        client.post("auth/login", json={"username": username, "password": password}).status_code
        == 204
    )
    client.headers.update(
        {
            "X-CSRF-Token": client.cookies["notes_csrf"],
            "Origin": base_url.rstrip("/").removesuffix("/api/v1"),
        }
    )
    return client


def elapsed(operation) -> tuple[float, httpx.Response]:
    started = monotonic()
    response = operation()
    return monotonic() - started, response


class TimedInternalRetrieval:
    def __init__(self) -> None:
        self.durations: list[float] = []
        self.item = RetrievalResult(uuid4(), "Release", "Friday at 2 PM", 0.95)

    async def search(self, _query: str):
        started = monotonic()
        result = [self.item]
        self.durations.append(monotonic() - started)
        return result


class RagModel:
    def __init__(self, note_id) -> None:
        self.note_id = note_id
        self.classify_next = True

    async def complete(self, _prompt: str, **_kwargs) -> str:
        if self.classify_next:
            self.classify_next = False
            return json.dumps({"intent": "rag"})
        self.classify_next = True
        return json.dumps(
            {"answer": "Friday at 2 PM", "citation_ids": [str(self.note_id)], "insufficient": False}
        )


@pytest.mark.asyncio
@pytest.mark.performance
async def test_retrieval_is_measured_internally_only_after_validated_rag_classification() -> None:
    retrieval = TimedInternalRetrieval()
    model = RagModel(retrieval.item.note_id)
    service = RagService(retrieval, model, intent=IntentService(model))
    responses = [
        await service.respond("According to my notes, when is release?") for _ in range(20)
    ]
    assert all(response.intent == "rag" and response.sources for response in responses)
    assert len(retrieval.durations) == 20
    assert p95(retrieval.durations) < 2


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
                            "notes",
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
                client.get(f"notes/{note_id}").json()["semantic_status"]
                for client, note_id in zip(clients, note_ids, strict=True)
            ]
            if all(status == "ready" for status in statuses):
                break
            sleep(0.5)
        assert all(status == "ready" for status in statuses)

        warmup_deadline = monotonic() + 180
        while True:
            warmup = clients[0].post(
                "chat/messages",
                json={"message": "What day and time is the software release?"},
            )
            if warmup.status_code == 200:
                break
            assert warmup.status_code == 503 and monotonic() < warmup_deadline
            sleep(2)

        for message, expected_intent in (
            ("According to my notes, what day and time is the software release?", "rag"),
            ("What is software release management?", "general_chat"),
        ):
            chat_durations = []
            for client in clients:
                duration, response = elapsed(
                    lambda current=client, query=message: current.post(
                        "chat/messages", json={"message": query}
                    )
                )
                assert response.status_code == 200
                assert response.json()["intent"] == expected_intent
                chat_durations.append(duration)
            assert sum(duration <= 60 for duration in chat_durations) / len(chat_durations) >= 0.9
    finally:
        for client in clients:
            client.close()
