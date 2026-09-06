"""Health endpoint and request-id plumbing."""


def test_health_reports_ok_with_request_id(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] == "ok"
    assert body["error"] is None
    assert response.headers["X-Request-ID"]


def test_client_supplied_request_id_is_echoed(client):
    response = client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"
