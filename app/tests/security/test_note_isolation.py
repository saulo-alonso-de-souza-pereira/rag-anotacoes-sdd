from fastapi.testclient import TestClient

from tests.integration.test_us1_api import authenticate, build_app


def headers(csrf: str, version: str | None = None) -> dict[str, str]:
    result = {"X-CSRF-Token": csrf}
    if version:
        result["If-Match"] = '"' + version + '"'
    return result


def test_anonymous_owner_other_user_matrix_for_note_operations() -> None:
    app = build_app()
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/notes").status_code == 401
        assert (
            anonymous.post("/api/v1/notes", json={"title": "x", "content": "x"}).status_code == 401
        )

    with TestClient(app) as alice, TestClient(app) as bob:
        alice_csrf, bob_csrf = authenticate(alice, "alice"), authenticate(bob, "bob")
        created = alice.post(
            "/api/v1/notes",
            json={"title": "Segredo", "content": "somente alice"},
            headers=headers(alice_csrf),
        )
        note = created.json()
        note_id = note["id"]
        assert alice.get("/api/v1/notes").json()["items"][0]["id"] == note_id
        assert bob.get("/api/v1/notes").json()["items"] == []
        assert alice.get("/api/v1/notes/" + note_id).status_code == 200
        for method in ("get", "patch", "delete"):
            if method == "get":
                response = bob.get("/api/v1/notes/" + note_id)
            elif method == "patch":
                response = bob.patch(
                    "/api/v1/notes/" + note_id,
                    json={"title": "roubado"},
                    headers=headers(bob_csrf, "1"),
                )
            else:
                response = bob.delete("/api/v1/notes/" + note_id, headers=headers(bob_csrf))
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "note_not_found"
        assert (
            alice.patch(
                "/api/v1/notes/" + note_id,
                json={"title": "Atualizado"},
                headers=headers(alice_csrf, "1"),
            ).status_code
            == 200
        )
        assert (
            alice.delete("/api/v1/notes/" + note_id, headers=headers(alice_csrf)).status_code == 204
        )
