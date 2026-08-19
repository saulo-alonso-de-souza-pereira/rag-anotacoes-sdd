import logging

from fastapi.testclient import TestClient

from tests.integration.test_us1_api import authenticate, build_app


def test_cookie_flags_csrf_origin_and_revocation() -> None:
    with TestClient(build_app()) as client:
        csrf = authenticate(client, "alice")
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "uma senha local segura"},
        )
        cookies = login.headers.get_list("set-cookie")
        session_cookie = next(value for value in cookies if value.startswith("notes_session="))
        assert "HttpOnly" in session_cookie
        assert "SameSite=strict" in session_cookie
        assert "Domain=" not in session_cookie
        csrf = client.cookies["notes_csrf"]
        payload = {"title": "T", "content": "C"}
        assert client.post("/api/v1/notes", json=payload).status_code == 403
        assert (
            client.post(
                "/api/v1/notes",
                json=payload,
                headers={"X-CSRF-Token": csrf, "Origin": "https://attacker.invalid"},
            ).status_code
            == 403
        )
        assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401


def test_login_failures_are_non_enumerating_and_rate_limited() -> None:
    with TestClient(build_app()) as client:
        authenticate(client, "alice")
        client.cookies.clear()
        missing = client.post(
            "/api/v1/auth/login",
            json={"username": "missing", "password": "senha incorreta longa"},
        )
        wrong = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "senha incorreta longa"},
        )
        assert missing.status_code == wrong.status_code == 401
        assert missing.json()["error"]["message"] == wrong.json()["error"]["message"]
        for _ in range(3):
            client.post(
                "/api/v1/auth/login",
                json={"username": "missing", "password": "senha incorreta longa"},
            )
        limited = client.post(
            "/api/v1/auth/login",
            json={"username": "missing", "password": "senha incorreta longa"},
        )
        assert limited.status_code == 429


def test_sensitive_values_are_not_logged(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    password = "senha-super-secreta"
    with TestClient(build_app()) as client:
        client.post("/api/v1/auth/register", json={"username": "alice", "password": password})
        client.post("/api/v1/auth/login", json={"username": "alice", "password": password})
    assert password not in caplog.text
    assert "notes_session=" not in caplog.text
