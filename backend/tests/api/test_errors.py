"""Every error path must produce the envelope and never leak internals."""

from fastapi.testclient import TestClient


def test_unknown_api_route_uses_envelope(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "http_error"


def test_mutation_without_csrf_header_is_rejected(app):
    bare_client = TestClient(app)
    response = bare_client.post("/api/health")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_missing"


def test_unexpected_exception_is_masked(app):
    @app.get("/api/boom")
    def boom():
        raise RuntimeError("secret detail")

    tolerant_client = TestClient(app, raise_server_exceptions=False)
    response = tolerant_client.get("/api/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret detail" not in response.text
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
