import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import Page, Route, expect

WEB = Path(__file__).resolve().parents[2] / "src/notes_rag/web"


@pytest.mark.e2e
def test_registration_crud_cancel_confirm_logout_and_reload(page: Page) -> None:
    state = {"registered": False, "logged": False, "notes": []}
    now = datetime.now(UTC).isoformat()

    def json_response(route: Route, status: int, payload=None) -> None:
        route.fulfill(
            status=status,
            content_type="application/json",
            body="" if payload is None else json.dumps(payload),
        )

    def handler(route: Route) -> None:
        path = route.request.url.split("app.test", 1)[-1]
        method = route.request.method
        if path == "/":
            route.fulfill(content_type="text/html", body=(WEB / "index.html").read_text("utf-8"))
        elif path == "/static/app.js":
            route.fulfill(content_type="text/javascript", body=(WEB / "app.js").read_text("utf-8"))
        elif path == "/static/styles.css":
            route.fulfill(content_type="text/css", body=(WEB / "styles.css").read_text("utf-8"))
        elif path == "/api/v1/auth/me":
            json_response(
                route, 200, {"id": str(uuid4()), "username": "alice", "created_at": now}
            ) if state["logged"] else json_response(
                route, 401, {"error": {"message": "Autenticação necessária."}}
            )
        elif path == "/api/v1/auth/register":
            state["registered"] = True
            json_response(route, 201, {"id": str(uuid4()), "username": "alice", "created_at": now})
        elif path == "/api/v1/auth/login":
            state["logged"] = state["registered"]
            route.fulfill(status=204, headers={"Set-Cookie": "notes_csrf=test; Path=/"})
        elif path == "/api/v1/auth/logout":
            state["logged"] = False
            route.fulfill(status=204)
        elif path == "/api/v1/notes" and method == "GET":
            json_response(route, 200, {"items": state["notes"], "next_cursor": None})
        elif path == "/api/v1/notes" and method == "POST":
            body = route.request.post_data_json
            note = {
                "id": str(uuid4()),
                **body,
                "version": 1,
                "semantic_status": "pending",
                "semantic_error_code": None,
                "created_at": now,
                "updated_at": now,
            }
            state["notes"].append(note)
            json_response(route, 201, note)
        elif path.startswith("/api/v1/notes/"):
            note_id = path.rsplit("/", 1)[-1]
            note = next((item for item in state["notes"] if item["id"] == note_id), None)
            if method == "GET":
                json_response(route, 200, note)
            elif method == "PATCH":
                note.update(route.request.post_data_json)
                note["version"] += 1
                json_response(route, 200, note)
            else:
                state["notes"] = [item for item in state["notes"] if item["id"] != note_id]
                route.fulfill(status=204)
        else:
            route.fulfill(status=404)

    page.route("**/*", handler)
    page.goto("http://app.test/")
    page.get_by_label("Nome de usuário").fill("alice")
    page.get_by_label("Senha").fill("uma senha local segura")
    page.get_by_role("button", name="Cadastrar").click()
    page.get_by_role("button", name="Entrar").click()
    page.get_by_label("Título").fill("Primeira nota")
    page.get_by_label("Conteúdo").fill("Conteúdo persistente")
    page.get_by_role("button", name="Salvar").click()
    page.reload()
    page.get_by_role("button", name="Primeira nota").click()
    expect(page.get_by_label("Título")).to_have_value("Primeira nota")
    page.get_by_label("Título").fill("Nota atualizada")
    page.get_by_role("button", name="Salvar").click()
    page.get_by_role("button", name="Nota atualizada").wait_for()
    page.evaluate("window.confirm = () => false")
    page.get_by_role("button", name="Excluir").click()
    page.get_by_role("button", name="Nota atualizada").wait_for()
    page.evaluate("window.confirm = () => true")
    page.get_by_role("button", name="Excluir").click()
    page.get_by_text("Nenhuma anotação.").wait_for()
    page.get_by_role("button", name="Sair").click()
    page.get_by_role("heading", name="Acessar").wait_for()
