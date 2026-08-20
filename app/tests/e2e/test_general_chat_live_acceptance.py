import os
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest

from notes_rag.services.rag import INSUFFICIENT


@pytest.mark.e2e
@pytest.mark.live_model
def test_quickstart_a_to_h_and_sc012_against_real_backend() -> None:
    base_url = os.getenv("NOTES_ACCEPTANCE_URL")
    if not base_url:
        pytest.skip("NOTES_ACCEPTANCE_URL is required for real backend acceptance")
    with httpx.Client(base_url=base_url.rstrip("/") + "/", timeout=70) as client:
        username = f"modes-{uuid4().hex[:12]}"
        password = "Senha local segura 2026!"
        assert (
            client.post(
                "auth/register", json={"username": username, "password": password}
            ).status_code
            == 201
        )
        assert (
            client.post("auth/login", json={"username": username, "password": password}).status_code
            == 204
        )
        headers = {
            "X-CSRF-Token": client.cookies["notes_csrf"],
            "Origin": base_url.rstrip("/").removesuffix("/api/v1"),
        }

        note = client.post(
            "notes",
            headers=headers,
            json={"title": "Docker", "content": "Docker executa aplicações em containers."},
        ).json()
        deadline = monotonic() + 30
        while monotonic() < deadline:
            current = client.get(f"notes/{note['id']}").json()
            if current["semantic_status"] == "ready":
                break
            sleep(0.5)
        assert current["semantic_status"] == "ready"

        rag = client.post(
            "chat/messages",
            headers=headers,
            json={"message": "O que eu anotei sobre Docker?"},
        )
        assert rag.status_code == 200
        assert rag.json()["intent"] == "rag"
        assert rag.json()["answer"] == INSUFFICIENT or rag.json()["sources"]

        for question in ("O que é Docker?", "O que é Kubernetes?", "Quem é Ada Lovelace?"):
            general = client.post("chat/messages", headers=headers, json={"message": question})
            assert general.status_code == 200
            assert general.json()["intent"] == "general_chat"
            assert general.json()["sources"] == []

        insufficient = client.post(
            "chat/messages",
            headers=headers,
            json={"message": "Segundo minhas notas, o que é Kubernetes?"},
        )
        assert insufficient.status_code == 200
        assert insufficient.json() == {
            "intent": "rag",
            "answer": INSUFFICIENT,
            "needs_clarification": False,
            "sources": [],
            "created_note": None,
        }

        before = client.get("notes").json()["items"]
        for message in (
            "Docker nas minhas notas ou em geral?",
            "Crie uma nota e explique Docker",
        ):
            clarification = client.post("chat/messages", headers=headers, json={"message": message})
            assert clarification.status_code == 200
            assert clarification.json()["intent"] == "clarification"
            assert clarification.json()["needs_clarification"] is True
            assert clarification.json()["sources"] == []
            assert clarification.json()["created_note"] is None
        assert len(client.get("notes").json()["items"]) == len(before)
