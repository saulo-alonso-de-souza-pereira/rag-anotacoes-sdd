import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import Page, Route, expect

WEB = Path(__file__).resolve().parents[2] / "src/notes_rag/web"


@pytest.mark.e2e
def test_general_and_grounded_indicators_sources_and_clarification(page: Page) -> None:
    now = datetime.now(UTC).isoformat()
    note_id = str(uuid4())
    note = {
        "id": note_id,
        "title": "Docker",
        "content": "Estudar containers",
        "version": 1,
        "semantic_status": "ready",
        "semantic_error_code": None,
        "created_at": now,
        "updated_at": now,
    }
    requests: list[str] = []

    def respond(route: Route, payload) -> None:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    def handler(route: Route) -> None:
        path = route.request.url.split("app.test", 1)[-1]
        if path == "/":
            route.fulfill(content_type="text/html", body=(WEB / "index.html").read_text("utf-8"))
        elif path == "/static/app.js":
            route.fulfill(content_type="text/javascript", body=(WEB / "app.js").read_text("utf-8"))
        elif path == "/static/styles.css":
            route.fulfill(content_type="text/css", body=(WEB / "styles.css").read_text("utf-8"))
        elif path == "/api/v1/auth/me":
            respond(route, {"id": str(uuid4()), "username": "alice", "created_at": now})
        elif path == "/api/v1/notes":
            respond(route, {"items": [note], "next_cursor": None})
        elif path.startswith("/api/v1/notes/"):
            respond(route, note)
        elif path == "/api/v1/chat/messages":
            message = route.request.post_data_json["message"]
            requests.append(message)
            if message == "O que é Docker?":
                respond(
                    route,
                    {
                        "intent": "general_chat",
                        "answer": "Docker é uma plataforma de containers.",
                        "needs_clarification": False,
                        "sources": [],
                        "created_note": None,
                    },
                )
            elif message == "O que eu anotei sobre Docker?":
                respond(
                    route,
                    {
                        "intent": "rag",
                        "answer": "Você anotou estudar containers.",
                        "needs_clarification": False,
                        "sources": [
                            {"note_id": note_id, "title": "Docker", "excerpt": "Estudar containers"}
                        ],
                        "created_note": None,
                    },
                )
            elif message == "Segundo minhas notas, o que é Kubernetes?":
                respond(
                    route,
                    {
                        "intent": "rag",
                        "answer": (
                            "Não encontrei informação suficiente nas suas anotações para responder."
                        ),
                        "needs_clarification": False,
                        "sources": [],
                        "created_note": None,
                    },
                )
            else:
                respond(
                    route,
                    {
                        "intent": "clarification",
                        "answer": "Escolha uma única intenção.",
                        "needs_clarification": True,
                        "sources": [],
                        "created_note": None,
                    },
                )
        else:
            route.fulfill(status=404)

    page.route("**/*", handler)
    page.goto("http://app.test/")
    page.get_by_role("button", name="Chat").click()
    message = page.get_by_label("Converse ou pergunte às suas anotações")

    message.fill("O que é Docker?")
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("Resposta geral")).to_be_visible()
    expect(page.get_by_role("heading", name="Fontes")).to_have_count(0)

    message.fill("O que eu anotei sobre Docker?")
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("Baseada nas suas anotações")).to_be_visible()
    expect(page.get_by_role("heading", name="Fontes")).to_be_visible()

    message.fill("Segundo minhas notas, o que é Kubernetes?")
    page.get_by_role("button", name="Enviar").click()
    expect(
        page.get_by_text("Não encontrei informação suficiente nas suas anotações para responder.")
    ).to_be_visible()
    expect(page.get_by_role("heading", name="Fontes")).to_have_count(0)

    message.fill("Crie uma nota e explique Docker")
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("Escolha uma única intenção.")).to_be_visible()
    expect(page.get_by_text("O chatbot precisa de mais informações.")).to_be_visible()
    assert requests == [
        "O que é Docker?",
        "O que eu anotei sobre Docker?",
        "Segundo minhas notas, o que é Kubernetes?",
        "Crie uma nota e explique Docker",
    ]


@pytest.mark.e2e
@pytest.mark.live_model
def test_real_backend_renders_general_and_grounded_modes(page: Page) -> None:
    base_url = os.getenv("NOTES_UI_URL")
    if not base_url:
        pytest.skip("NOTES_UI_URL is required for real browser acceptance")
    username = f"browser-{uuid4().hex[:12]}"
    password = "Senha local segura 2026!"
    page.goto(base_url)
    page.get_by_label("Nome de usuário").fill(username)
    page.get_by_label("Senha").fill(password)
    page.get_by_role("button", name="Cadastrar").click()
    expect(page.get_by_text("Cadastro concluído. Agora entre.")).to_be_visible()
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("heading", name="Minhas anotações")).to_be_visible()

    page.get_by_role("button", name="Chat").click()
    message = page.get_by_label("Converse ou pergunte às suas anotações")
    message.fill("O que é Docker?")
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("Resposta geral")).to_be_visible(timeout=70_000)
    expect(page.get_by_role("heading", name="Fontes")).to_have_count(0)

    page.get_by_role("button", name="Anotações").click()
    page.get_by_label("Título").fill("Docker")
    page.get_by_label("Conteúdo").fill("Docker executa aplicações em containers.")
    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_text("ready")).to_be_visible(timeout=30_000)
    page.get_by_role("button", name="Chat").click()
    page.get_by_label("Converse ou pergunte às suas anotações").fill(
        "O que eu anotei sobre Docker?"
    )
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("Baseada nas suas anotações")).to_be_visible(timeout=70_000)
    expect(page.get_by_role("heading", name="Fontes")).to_be_visible()
