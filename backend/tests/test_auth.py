from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.api.deps import get_auth_service
from app.config import Settings, get_settings
from app.main import app
from app.services.auth_service import AuthError, AuthService, RegistrationClosedError

SETTINGS = Settings(jwt_secret="test-secret")


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def service(repo):
    return AuthService(repo, SETTINGS)


def make_user(service, password="correct-horse", uid=1):
    return SimpleNamespace(
        id=uid, email="a@b.co", password_hash=service.hash_password(password)
    )


def test_password_hash_is_argon2_and_verifies(service):
    h = service.hash_password("s3cretpass")
    assert h.startswith("$argon2")
    assert service.verify_password("s3cretpass", h)
    assert not service.verify_password("wrong", h)
    assert not service.verify_password("x", "not-a-hash")


def test_token_roundtrip(service):
    token = service.issue_token(SimpleNamespace(id=7))
    assert service.verify_token(token) == 7


def test_token_rejects_tampered_wrong_secret_and_expired(service):
    with pytest.raises(AuthError):
        service.verify_token("garbage")
    other = jwt.encode({"sub": "1"}, "other-secret", algorithm="HS256")
    with pytest.raises(AuthError):
        service.verify_token(other)
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        SETTINGS.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(AuthError):
        service.verify_token(expired)


def test_register_once(service, repo):
    repo.count.return_value = 1
    with pytest.raises(RegistrationClosedError):
        service.register("a@b.co", "password123")
    repo.create.assert_not_called()
    repo.count.return_value = 0
    service.register("a@b.co", "password123")
    email, pw_hash = repo.create.call_args.args
    assert email == "a@b.co" and pw_hash.startswith("$argon2")


def test_login_success_and_failures(service, repo):
    user = make_user(service)
    repo.get_by_email.return_value = user
    _, token = service.login("a@b.co", "correct-horse")
    assert service.verify_token(token) == 1
    with pytest.raises(AuthError):
        service.login("a@b.co", "bad-password")
    repo.get_by_email.return_value = None
    with pytest.raises(AuthError):
        service.login("none@b.co", "correct-horse")


@pytest.fixture
def client(service, repo):
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_protected_route_rejects_unauthenticated(client):
    assert client.get("/auth/me").status_code == 401


def test_protected_route_rejects_bad_token(client):
    client.cookies.set(SETTINGS.auth_cookie_name, "garbage")
    assert client.get("/auth/me").status_code == 401


def test_login_sets_httponly_cookie_then_me_and_logout(client, service, repo):
    user = make_user(service)
    repo.get_by_email.return_value = user
    repo.get_by_id.return_value = user
    r = client.post(
        "/auth/login", json={"email": "a@b.co", "password": "correct-horse"}
    )
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert client.get("/auth/me").json()["email"] == "a@b.co"
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_login_bad_password_401(client, service, repo):
    repo.get_by_email.return_value = make_user(service)
    r = client.post("/auth/login", json={"email": "a@b.co", "password": "wrong-pass1"})
    assert r.status_code == 401


def test_register_closed_403(client, repo):
    repo.count.return_value = 1
    r = client.post("/auth/register", json={"email": "a@b.co", "password": "password123"})
    assert r.status_code == 403
