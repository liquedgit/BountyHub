import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import get_db
from app.main import create_app

HEADERS = {
    "x-content-type-options": "nosniff",
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_are_closed_by_default(client, path):
    assert client.get(path).status_code == 404


def test_docs_open_when_exposed(monkeypatch):
    monkeypatch.setenv("EXPOSE_DOCS", "true")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as c:
            assert c.get("/openapi.json").status_code == 200
    finally:
        get_settings.cache_clear()


def test_security_headers_on_normal_and_error_responses(client):
    for resp in (client.get("/health"), client.get("/auth/me"), client.get("/nope")):
        for name, value in HEADERS.items():
            assert resp.headers[name] == value


def test_validation_error_does_not_echo_input(client):
    resp = client.post("/auth/register", json={"email": "a@b.co", "password": "short"})
    assert resp.status_code == 422
    items = resp.json()["detail"]
    assert items and all(set(i) == {"type", "loc", "msg"} for i in items)
    assert '"input"' not in resp.text and '"ctx"' not in resp.text
    assert '"short"' not in resp.text
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_unhandled_exception_is_a_generic_500(db_session):
    app = create_app()
    router = APIRouter()

    @router.get("/boom")
    def boom():
        raise RuntimeError("secret-internal-detail")

    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/boom")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert "secret-internal-detail" not in resp.text
    for name, value in HEADERS.items():
        assert resp.headers[name] == value


def test_no_cors_headers_for_foreign_origin(client):
    resp = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in resp.headers
    pre = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in pre.headers


@pytest.mark.parametrize("url", ["ftp://x/v1", "javascript:alert(1)", "not a url"])
def test_openai_base_url_must_be_http(auth_client, url):
    resp = auth_client.put("/settings/ai", json={"openai_base_url": url})
    assert resp.status_code == 422
    assert url not in resp.text


def test_openai_base_url_accepts_https(auth_client):
    resp = auth_client.put("/settings/ai", json={"openai_base_url": "https://api.example.com/v1"})
    assert resp.status_code == 200
