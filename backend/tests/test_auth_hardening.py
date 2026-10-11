from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.api.deps import get_auth_service
from app.core.config import Settings, check_secrets, get_settings
from app.main import create_app
from app.services.auth_service import AuthService
from app.services.login_throttle import LoginThrottle

SECRET = get_settings().jwt_secret
LOGIN = "/auth/login"


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def service(repo):
    return AuthService(repo, get_settings())


@pytest.fixture
def api(service, repo, clock):
    app = create_app()
    app.state.login_throttle = LoginThrottle(5, 900, 50, clock=clock)
    app.dependency_overrides[get_auth_service] = lambda: service
    user = MagicMock(id=1, email="a@b.co", password_hash=service.hash_password("correct-horse"))
    repo.get_by_email.return_value = user
    repo.get_by_id.return_value = user
    return TestClient(app)


def attempt(api, password="wrong-pass1", ip="1.1.1.1", email="a@b.co", **headers):
    headers.setdefault("X-Forwarded-For", ip)
    return api.post(LOGIN, json={"email": email, "password": password}, headers=headers)


def lock(api, ip="1.1.1.1"):
    for _ in range(5):
        assert attempt(api, ip=ip).status_code == 401


def test_sixth_failure_is_429_with_retry_after(api):
    lock(api)
    r = attempt(api)
    assert r.status_code == 429
    assert r.json() == {"detail": "Too many login attempts. Try again later."}
    assert 0 < int(r.headers["retry-after"]) <= 900


def test_correct_password_while_locked_is_429(api):
    lock(api)
    assert attempt(api, password="correct-horse").status_code == 429


def test_other_client_unaffected(api):
    lock(api)
    assert attempt(api, password="correct-horse", ip="2.2.2.2").status_code == 200


def test_success_resets_count(api):
    for _ in range(4):
        attempt(api)
    assert attempt(api, password="correct-horse").status_code == 200
    for _ in range(5):
        assert attempt(api).status_code == 401
    assert attempt(api).status_code == 429


def test_window_expiry(api, clock):
    lock(api)
    assert attempt(api).status_code == 429
    clock.now += 901
    assert attempt(api, password="correct-horse").status_code == 200


def test_global_ceiling(api, clock):
    for i in range(50):
        assert attempt(api, ip=f"10.0.{i // 200}.{i % 200}").status_code == 401
    r = attempt(api, password="correct-horse", ip="9.9.9.9")
    assert r.status_code == 429 and "retry-after" in r.headers
    clock.now += 901
    assert attempt(api, password="correct-horse", ip="9.9.9.9").status_code == 200


def test_client_key_header_precedence(api):
    # CF-Connecting-IP wins over X-Forwarded-For
    for _ in range(5):
        attempt(api, **{"CF-Connecting-IP": "7.7.7.7", "X-Forwarded-For": "1.1.1.1"})
    again = attempt(api, **{"CF-Connecting-IP": "7.7.7.7", "X-Forwarded-For": "3.3.3.3"})
    assert again.status_code == 429
    assert attempt(api, ip="1.1.1.1").status_code == 401
    # last hop of X-Forwarded-For is used, spoofed first hops are ignored
    for i in range(5):
        attempt(api, **{"X-Forwarded-For": f"6.6.6.{i}, 8.8.8.8"})
    assert attempt(api, **{"X-Forwarded-For": "5.5.5.5, 8.8.8.8"}).status_code == 429
    # no headers: peer address
    for _ in range(5):
        api.post(LOGIN, json={"email": "a@b.co", "password": "wrong-pass1"})
    r = api.post(LOGIN, json={"email": "a@b.co", "password": "wrong-pass1"})
    assert r.status_code == 429


def test_unknown_email_same_401_and_spends_a_verification(api, repo, service, monkeypatch):
    wrong = attempt(api)
    repo.get_by_email.return_value = None
    calls = []
    real = service.verify_password
    monkeypatch.setattr(
        service, "verify_password", lambda pw, h: calls.append(h) or real(pw, h)
    )
    unknown = attempt(api, email="nobody@b.co", ip="4.4.4.4")
    assert (unknown.status_code, unknown.json()) == (wrong.status_code, wrong.json())
    assert calls == [AuthService._dummy_hash]


# --- JWT checks ---
def token_with(secret=SECRET, alg="HS256", exp_delta=timedelta(hours=1)):
    claims = {"sub": "1", "exp": datetime.now(UTC) + exp_delta}
    return jwt.encode(claims, secret, algorithm=alg)


def none_alg_token():
    import base64
    import json
    import time

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    header = b64({"alg": "none", "typ": "JWT"})
    payload = b64({"sub": "1", "exp": int(time.time()) + 3600})
    return f"{header}.{payload}."


@pytest.mark.parametrize(
    "make",
    [
        lambda: token_with()[:-3] + "AAA",
        lambda: token_with(exp_delta=timedelta(minutes=-1)),
        lambda: token_with(secret="x" * 40),
        none_alg_token,
        lambda: "not.a.jwt",
        lambda: "garbage",
    ],
    ids=["tampered", "expired", "other-secret", "alg-none", "dotted-garbage", "garbage"],
)
def test_bad_jwt_is_401(api, make):
    api.cookies.set(get_settings().auth_cookie_name, make())
    assert api.get("/auth/me").status_code == 401


def test_valid_jwt_accepted(api):
    api.cookies.set(get_settings().auth_cookie_name, token_with())
    assert api.get("/auth/me").status_code == 200


# --- secret check ---
@pytest.mark.parametrize("secret", ["short", "change-me", "change-me-" + "x" * 40, "x" * 31])
def test_weak_secret_refused_outside_development(secret):
    with pytest.raises(RuntimeError) as exc:
        check_secrets(Settings(app_env="production", jwt_secret=secret))
    assert "JWT_SECRET" in str(exc.value)
    assert secret == "change-me" or secret not in str(exc.value)


def test_strong_secret_ok_and_development_exempt():
    check_secrets(Settings(app_env="production", jwt_secret="k" * 32))
    check_secrets(Settings(app_env="development", jwt_secret="change-me"))


def test_create_app_refuses_weak_secret(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_settings", lambda: Settings(app_env="production", jwt_secret="change-me")
    )
    with pytest.raises(RuntimeError):
        create_app()
