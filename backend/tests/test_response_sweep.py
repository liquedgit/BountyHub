import re

from app.core.config import get_settings
from app.main import create_app
from app.models import (
    Finding,
    Note,
    Program,
    ReconAsset,
    ReconJob,
    ScopeRule,
    Target,
)
from tests.test_route_protection import _all_endpoints

PASSWORD = "SENTINEL-password-7f3a9c"
CLAUDE_TOKEN = "SENTINEL-claude-token-4d2e"
OPENAI_KEY = "SENTINEL-openai-key-91bb"
FORBIDDEN_PROPS = {"password", "hashed_password", "token", "access_token", "api_key", "secret"}


def _seed(db):
    program = Program(name="P")
    db.add(program)
    db.flush()
    target = Target(program_id=program.id, value="example.com")
    rule = ScopeRule(program_id=program.id, action="in", type="domain", value="example.com")
    db.add_all([target, rule])
    db.flush()
    finding = Finding(program_id=program.id, target_id=target.id, title="F")
    db.add(finding)
    db.flush()
    db.add(Note(program_id=program.id, finding_id=finding.id, title="N"))
    job = ReconJob(program_id=program.id)
    db.add(job)
    db.flush()
    db.add(ReconAsset(job_id=job.id, asset_type="subdomain", value="a.example.com"))
    db.commit()


def test_no_credential_in_any_get_response(client, db_session):
    email = "sweep@example.com"
    creds = {"email": email, "password": PASSWORD}
    assert client.post("/auth/register", json=creds).status_code == 201
    login = client.post("/auth/login", json=creds)
    assert login.status_code == 200
    jwt_token = client.cookies.get(get_settings().auth_cookie_name)
    assert jwt_token
    put = client.put(
        "/settings/ai",
        json={
            "provider": "claude",
            "claude_token": CLAUDE_TOKEN,
            "openai_api_key": OPENAI_KEY,
            "openai_base_url": "https://api.example.com/v1",
        },
    )
    assert put.status_code == 200
    _seed(db_session)

    forbidden = [PASSWORD, CLAUDE_TOKEN, OPENAI_KEY, "$argon2", jwt_token]
    app = create_app()
    gets = [p for m, p in _all_endpoints(app) if m == "GET"]
    assert len(gets) > 5
    for path in gets:
        url = re.sub(r"\{[^}]+\}", "1", path)
        resp = client.get(url)
        assert resp.status_code < 500, url
        assert resp.status_code != 401, url
        for secret in forbidden:
            assert secret not in resp.text, f"{url} leaks {secret[:12]}"
    # The write response must not echo credentials either.
    for secret in forbidden[:3]:
        assert secret not in put.text


def _property_names(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                yield from value
            yield from _property_names(value)
    elif isinstance(node, list):
        for item in node:
            yield from _property_names(item)


def test_no_response_schema_exposes_credential_fields(monkeypatch):
    monkeypatch.setenv("EXPOSE_DOCS", "true")
    get_settings.cache_clear()
    try:
        spec = create_app().openapi()
    finally:
        get_settings.cache_clear()
    for name, schema in spec["components"]["schemas"].items():
        # Request bodies legitimately carry credentials; only *Response/Read/Out types matter.
        if name in {"Credentials", "AISettingsUpdate"} or name.startswith(
            ("Body_", "HTTPValidation", "ValidationError")
        ):
            continue
        bad = FORBIDDEN_PROPS & set(_property_names(schema))
        assert not bad, f"{name} exposes {bad}"
