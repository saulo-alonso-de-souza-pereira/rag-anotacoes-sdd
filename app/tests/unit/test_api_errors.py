from fastapi import FastAPI
from fastapi.testclient import TestClient

from notes_rag.api.errors import ApiError, install_error_handlers


def make_client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/failure")
    async def failure() -> None:
        raise ApiError(status_code=400, code="safe_failure", message="Falha segura")

    @app.get("/unexpected")
    async def unexpected() -> None:
        raise RuntimeError("password=hunter2")

    return TestClient(app, raise_server_exceptions=False)


def test_api_error_uses_uniform_envelope_and_request_id() -> None:
    response = make_client().get("/failure")
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    assert response.json()["error"]["code"] == "safe_failure"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_unexpected_error_does_not_expose_sensitive_detail() -> None:
    response = make_client().get("/unexpected")
    assert response.status_code == 500
    body = response.text
    assert "hunter2" not in body
    assert "RuntimeError" not in body
    assert response.json()["error"]["code"] == "internal_error"
