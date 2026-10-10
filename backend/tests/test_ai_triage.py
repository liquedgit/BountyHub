import json

import httpx
import pytest

from app.ai import AIProvider, AIProviderError, ClaudeProvider, OpenAICompatibleProvider
from app.ai.factory import AIProviderFactory
from app.api import triage as triage_api
from app.models import ReconAsset
from app.repositories.recon_asset import ReconAssetRepository
from app.repositories.settings import SettingsRepository
from app.services.ai_triage import AITriageService, parse_triage_reply


class FakeProvider(AIProvider):
    name = "fake"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


@pytest.fixture
def assets(db_session):
    rows = [
        ReconAsset(job_id=1, asset_type="subdomain", value="admin.example.com"),
        ReconAsset(job_id=1, asset_type="secret", value="AKIAIOSFODNN7EXAMPLEKEY1234"),
        ReconAsset(job_id=1, asset_type="secret", value="changeme_placeholder_value"),
        ReconAsset(job_id=2, asset_type="endpoint", value="/api/other"),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def test_factory_selects_claude(db_session):
    s = SettingsRepository(db_session)
    s.set("ai.provider", "claude")
    s.set("ai.claude.token", "tok")
    assert isinstance(AIProviderFactory(s).create(), ClaudeProvider)


def test_factory_selects_openai(db_session):
    s = SettingsRepository(db_session)
    s.set("ai.provider", "openai_compatible")
    s.set("ai.openai.base_url", "http://localhost:11434/v1")
    s.set("ai.openai.api_key", "k")
    s.set("ai.openai.model", "m")
    assert isinstance(AIProviderFactory(s).create(), OpenAICompatibleProvider)


def test_factory_errors_when_unconfigured(db_session):
    s = SettingsRepository(db_session)
    with pytest.raises(AIProviderError):
        AIProviderFactory(s).create()
    s.set("ai.provider", "claude")
    with pytest.raises(AIProviderError):
        AIProviderFactory(s).create()


def test_triage_scores_ranks_and_persists(db_session, assets):
    reply = "```json\n" + json.dumps([
        {"id": assets[0].id, "score": 40, "label": "interesting", "reason": "admin host"},
        {"id": assets[1].id, "score": 95, "label": "likely_secret", "reason": "AWS key"},
        {"id": assets[2].id, "score": 5, "label": "false_positive", "reason": "placeholder"},
        {"id": 9999, "score": 100, "label": "likely_secret", "reason": "invented"},
    ]) + "\n```"
    provider = FakeProvider(reply)
    result = AITriageService(provider, ReconAssetRepository(db_session)).triage(job_id=1)

    assert [r.id for r in result] == [assets[1].id, assets[0].id, assets[2].id]
    assert result[0].label == "likely_secret"
    assert result[-1].label == "false_positive"
    db_session.refresh(assets[1])
    assert assets[1].ai_score == 95 and assets[1].ai_label == "likely_secret"
    # job 2 asset untouched and not sent to the provider
    assert assets[3].ai_score is None
    assert "/api/other" not in provider.prompts[0]
    # secrets are redacted in the prompt
    assert "AKIAIOSFODNN7EXAMPLEKEY1234" not in provider.prompts[0]


def test_parse_rejects_garbage():
    with pytest.raises(AIProviderError):
        parse_triage_reply("no json here")


def test_claude_provider_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hi"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = ClaudeProvider("sk-token", model="m", client=client).complete("sys", "p")
    assert out == "hi"
    assert seen["auth"] == "Bearer sk-token"
    assert seen["body"]["system"] == "sys"


def test_openai_provider_request_and_error_hides_key():
    def ok(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://x/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "yo"}}]})

    client = httpx.Client(transport=httpx.MockTransport(ok))
    p = OpenAICompatibleProvider("http://x/v1/", "secret-key", "m", client=client)
    assert p.complete("s", "u") == "yo"

    bad = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    p = OpenAICompatibleProvider("http://x/v1", "secret-key", "m", client=bad)
    with pytest.raises(AIProviderError) as exc:
        p.complete("s", "u")
    assert "secret-key" not in str(exc.value)


def test_settings_endpoints_never_return_credentials(client):
    resp = client.put(
        "/settings/ai",
        json={"provider": "openai_compatible", "openai_base_url": "http://x/v1",
              "openai_api_key": "super-secret", "openai_model": "m"},
    )
    assert resp.status_code == 200
    assert "super-secret" not in resp.text
    body = client.get("/settings/ai").json()
    assert body["provider"] == "openai_compatible"
    assert body["openai_api_key_set"] is True
    assert body["claude_token_set"] is False
    assert client.put("/settings/ai", json={"provider": "bogus"}).status_code == 422


def test_triage_endpoint_wiring(client, assets, monkeypatch):
    # no provider configured -> 409
    assert client.post("/triage", json={"job_id": 1}).status_code == 409

    client.put("/settings/ai", json={"provider": "claude", "claude_token": "t"})
    reply = json.dumps([{"id": assets[1].id, "score": 90, "label": "likely_secret", "reason": "r"}])
    monkeypatch.setattr(
        triage_api.AIProviderFactory, "create", lambda self: FakeProvider(reply)
    )
    resp = client.post("/triage", json={"job_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "fake"
    assert body["assets"][0]["id"] == assets[1].id
    assert body["assets"][0]["label"] == "likely_secret"
