import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import Page, Route, expect

WEB = Path(__file__).resolve().parents[2] / "src/notes_rag/web"


@pytest.mark.e2e
def test_chat_clear_creation_clarification_question_and_note_discovery(page: Page) -> None:
    now = datetime.now(UTC).isoformat()
    state = {"notes": []}

    def respond(route: Route, status: int, payload=None) -> None:
        route.fulfill(
            status=status,
            content_type="application/json",
            body="" if payload is None else json.dumps(payload),
        )

    def handler(route: Route) -> None:
        path = route.request.url.split("app.test", 1)[-1]
        if path == "/":
            route.fulfill(content_type="text/html", body=(WEB / "index.html").read_text("utf-8"))
        elif path == "/static/app.js":
            route.fulfill(content_type="text/javascript", body=(WEB / "app.js").read_text("utf-8"))
        elif path == "/static/styles.css":
            route.fulfill(content_type="text/css", body=(WEB / "styles.css").read_text("utf-8"))
        elif path == "/api/v1/auth/me":
            respond(route, 200, {"id": str(uuid4()), "username": "alice", "created_at": now})
        elif path == "/api/v1/notes":
            respond(route, 200, {"items": state["notes"], "next_cursor": None})
        elif path.startswith("/api/v1/notes/"):
            note_id = path.rsplit("/", 1)[-1]
            respond(route, 200, next(note for note in state["notes"] if note["id"] == note_id))
        elif path == "/api/v1/chat/messages":
            message = route.request.post_data_json["message"]
            if message == "Crie uma nota de compras":
                note = {
                    "id": str(uuid4()),
                    "title": "Compras",
                    "content": "Comprar café",
                    "version": 1,
                    "semantic_status": "pending",
                    "semantic_error_code": None,
                    "created_at": now,
                    "updated_at": now,
                }
                state["notes"].append(note)
                respond(
                    route,
                    200,
                    {
                        "intent": "create_note",
                        "answer": "Anotação criada.",
                        "needs_clarification": False,
                        "sources": [],
                        "created_note": note,
                    },
                )
            elif message == "Anote isso":
                respond(
                    route,
                    200,
                    {
                        "intent": "create_note",
                        "answer": "Qual título e conteúdo?",
                        "needs_clarification": True,
                        "sources": [],
                        "created_note": None,
                    },
                )
            else:
                respond(
                    route,
                    200,
                    {
                        "intent": "rag",
                        "answer": "Não encontrei informação suficiente.",
                        "needs_clarification": False,
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
    message.fill("Crie uma nota de compras")
    page.get_by_role("button", name="Enviar").click()
    page.get_by_role("link", name="Abrir anotação criada").click()
    expect(page.get_by_label("Título")).to_have_value("Compras")
    assert len(state["notes"]) == 1

    page.get_by_role("button", name="Chat").click()
    page.get_by_label("Converse ou pergunte às suas anotações").fill("Anote isso")
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("O chatbot precisa de mais informações.")).to_be_visible()
    page.get_by_label("Converse ou pergunte às suas anotações").fill("Qual minha comida favorita?")
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("Não encontrei informação suficiente.")).to_be_visible()
    assert len(state["notes"]) == 1
