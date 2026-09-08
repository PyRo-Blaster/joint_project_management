"""The built SPA is served with a client-side-routing fallback that never shadows the API."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.constants import CSRF_HEADER, CSRF_VALUE
from app.main import create_app


def test_spa_fallback_and_api_404(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>CMC</title>", encoding="utf-8")
    monkeypatch.setenv("STATIC_DIR", str(static))
    get_settings.cache_clear()
    try:
        client = TestClient(create_app(), headers={CSRF_HEADER: CSRF_VALUE})

        # A deep client-side route returns the SPA shell.
        deep = client.get("/items/42")
        assert deep.status_code == 200
        assert "text/html" in deep.headers["content-type"]
        assert "<title>CMC</title>" in deep.text

        # An unknown API route still returns the JSON envelope 404, not the SPA.
        missing = client.get("/api/does-not-exist")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "http_error"
    finally:
        get_settings.cache_clear()
