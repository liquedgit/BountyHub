import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_db
from app.jobs import recon_jobs
from app.main import create_app
from app.models import Program, ReconJob, ScopeRule
from app.recon.base import AssetType, ReconAssetResult, ReconTool
from app.recon.runner import ToolError
from app.services.recon import ReconService, ScopeViolation


class FakeTool(ReconTool):
    def __init__(self, name, results=(), error=None):
        self.name = name
        self.results, self.error, self.calls = list(results), error, []

    def run(self, targets):
        targets = list(targets)
        self.calls.append(targets)
        if self.error:
            raise self.error
        return list(self.results)


class FakeQueue:
    def __init__(self, fail=False):
        self.jobs, self.fail = [], fail

    async def enqueue_recon_job(self, job_id):
        if self.fail:
            raise RuntimeError("redis down")
        self.jobs.append(job_id)


def sub(value):
    return ReconAssetResult(AssetType.SUBDOMAIN, value, "subfinder", {"input": "example.com"})


def host(value):
    return ReconAssetResult(AssetType.HOST, value, "httpx", {"status_code": 200})


@pytest.fixture
def program(db_session):
    p = Program(name="P")
    p.scope_rules = [
        ScopeRule(action="in", type="domain", value="example.com"),
        ScopeRule(action="in", type="wildcard", value="*.example.com"),
        ScopeRule(action="out", type="domain", value="admin.example.com"),
    ]
    db_session.add(p)
    db_session.commit()
    return p


def service(db, subfinder=None, httpx=None):
    return ReconService(db, subfinder or FakeTool("subfinder"), httpx or FakeTool("httpx"))


def test_create_job_partitions_targets(db_session, program):
    job = service(db_session).create_job(program.id, ["example.com", "evil.com", "example.com"])
    assert job.status == "queued"
    assert job.targets == ["example.com"]
    assert job.rejected_targets == ["evil.com"]


def test_create_job_all_out_of_scope_raises(db_session, program):
    with pytest.raises(ScopeViolation) as exc:
        service(db_session).create_job(program.id, ["evil.com", "admin.example.com"])
    assert exc.value.rejected_targets == ["evil.com", "admin.example.com"]
    assert db_session.query(ReconJob).count() == 0


def test_run_job_filters_discovered_hosts_before_httpx(db_session, program):
    subfinder = FakeTool("subfinder", [sub("api.example.com"), sub("admin.example.com"),
                                       sub("x.evil.net")])
    httpx = FakeTool("httpx", [host("https://api.example.com"), host("https://evil.net")])
    svc = service(db_session, subfinder, httpx)
    job = svc.create_job(program.id, ["example.com", "evil.com"])
    svc.run_job(job.id)

    assert subfinder.calls == [["example.com"]]
    assert httpx.calls == [["example.com", "api.example.com"]]
    db_session.refresh(job)
    assert job.status == "completed" and job.error is None and job.current_stage is None
    assert job.finished_at is not None
    assert job.rejected_targets == ["evil.com", "admin.example.com", "x.evil.net", "https://evil.net"]
    assets = svc.list_assets(job.id)
    assert [(a.asset_type, a.value) for a in assets] == [
        ("subdomain", "api.example.com"),
        ("host", "https://api.example.com"),
    ]


def test_run_job_reloads_scope_rules(db_session, program):
    subfinder, httpx = FakeTool("subfinder"), FakeTool("httpx")
    svc = service(db_session, subfinder, httpx)
    job = svc.create_job(program.id, ["example.com"])
    program.scope_rules[0].action = "out"  # rule changed after job creation
    db_session.commit()
    svc.run_job(job.id)
    db_session.refresh(job)
    assert subfinder.calls == [] and httpx.calls == []
    assert job.status == "failed" and "in scope" in job.error
    assert job.rejected_targets == ["example.com"]


def test_run_job_tool_failure_marks_failed(db_session, program):
    subfinder = FakeTool("subfinder", error=ToolError("tool not found: subfinder"))
    httpx = FakeTool("httpx")
    svc = service(db_session, subfinder, httpx)
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)  # must not raise
    db_session.refresh(job)
    assert job.status == "failed" and "tool not found" in job.error
    assert httpx.calls == []


def test_run_job_unknown_job_is_noop(db_session):
    service(db_session).run_job(999)


@pytest.fixture
def queue():
    return FakeQueue()


@pytest.fixture
def api(db_session, queue):
    app = create_app(job_queue=queue)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: object()
    with TestClient(app) as c:
        yield c


def test_post_scan_accepted_and_enqueued(api, db_session, program, queue):
    r = api.post("/recon/scans", json={"program_id": program.id,
                                       "targets": ["example.com", "evil.com"]})
    assert r.status_code == 202
    body = r.json()
    assert body["targets"] == ["example.com"] and body["rejected_targets"] == ["evil.com"]
    assert body["status"] == "queued"
    assert queue.jobs == [body["id"]]
    assert api.get(f"/recon/scans/{body['id']}").json()["id"] == body["id"]


def test_post_scan_nothing_in_scope_422(api, program, queue):
    r = api.post("/recon/scans", json={"program_id": program.id, "targets": ["evil.com"]})
    assert r.status_code == 422
    assert r.json()["rejected_targets"] == ["evil.com"]
    assert queue.jobs == []


def test_post_scan_unknown_program_404(api):
    r = api.post("/recon/scans", json={"program_id": 99, "targets": ["example.com"]})
    assert r.status_code == 404


def test_enqueue_failure_marks_job_failed(db_session, program):
    app = create_app(job_queue=FakeQueue(fail=True))
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: object()
    with TestClient(app) as c:
        r = c.post("/recon/scans", json={"program_id": program.id, "targets": ["example.com"]})
    assert r.status_code == 503
    assert db_session.query(ReconJob).one().status == "failed"


def test_assets_endpoint_field_names(api, db_session, program):
    svc = service(db_session, FakeTool("subfinder", [sub("api.example.com")]), FakeTool("httpx"))
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)
    asset = svc.list_assets(job.id)[0]
    asset.ai_score = 0.7
    db_session.commit()
    r = api.get(f"/recon/scans/{job.id}/assets")
    assert r.status_code == 200
    assert r.json() == [{
        "id": asset.id, "asset_type": "subdomain", "value": "api.example.com",
        "source": "subfinder", "meta": {"input": "example.com"}, "triage_score": 0.7,
    }]
    assert api.get("/recon/scans/999/assets").status_code == 404
    assert api.get("/recon/scans/999").status_code == 404


def test_recon_routes_require_auth(db_session, queue):
    app = create_app(job_queue=queue)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        resp = c.post("/recon/scans", json={"program_id": 1, "targets": ["a.com"]})
        assert resp.status_code == 401
        assert c.get("/recon/scans/1").status_code == 401
        assert c.get("/recon/scans/1/assets").status_code == 401


def test_arq_job_wraps_service_in_thread(monkeypatch):
    import asyncio

    seen = []
    monkeypatch.setattr(recon_jobs, "_run_sync", seen.append)
    assert asyncio.run(recon_jobs.run_recon_job({}, 5)) == 5
    assert seen == [5]


def test_worker_registers_recon_job():
    from app.worker import WorkerSettings

    assert recon_jobs.run_recon_job in WorkerSettings.functions


# --- JS crawl, secret scan and AI triage stages ---

from app.ai.base import AIProvider, AIProviderError  # noqa: E402
from app.recon.fetcher import HttpFetcher  # noqa: E402
from app.recon.scope import ScopeValidator  # noqa: E402

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
PAGES = {
    "https://api.example.com": '<script src="/app.js"></script>',
    "https://api.example.com/app.js": f'fetch("/api/users"); var k = "{AWS_KEY}";',
}


class FakeFetcher:
    def __init__(self, pages=None):
        self.pages, self.calls = PAGES if pages is None else pages, []

    def __call__(self, url):
        self.calls.append(url)
        return self.pages.get(url)


class FakeAI(AIProvider):
    name = "fake"

    def __init__(self, error=None):
        self.error, self.prompts = error, []

    def complete(self, system, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        import json

        return json.dumps([{"id": a["id"], "score": 50, "label": "interesting", "reason": "r"}
                           for a in json.loads(prompt)])


def full_service(db, fetcher=None, ai=None):
    httpx = FakeTool("httpx", [host("https://api.example.com")])
    fetcher = fetcher or FakeFetcher()
    def ai_factory():
        if ai is None:
            raise AIProviderError("No AI provider selected")
        return ai

    return ReconService(db, FakeTool("subfinder"), httpx,
                        fetcher_factory=lambda scope: fetcher, ai_provider_factory=ai_factory)


def test_full_pipeline_stores_all_asset_types_and_orders_stages(db_session, program, monkeypatch):
    from app.repositories.recon_job import ReconJobRepository

    stages = []
    orig = ReconJobRepository.set_stage
    monkeypatch.setattr(ReconJobRepository, "set_stage",
                        lambda self, job, st: (stages.append(st), orig(self, job, st))[1])
    ai = FakeAI()
    svc = full_service(db_session, ai=ai)
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)
    db_session.refresh(job)

    assert stages == ["subfinder", "httpx", "js_crawler", "secret_scanner", "triage"]
    assert job.status == "completed" and job.error is None and job.notes == []
    assets = svc.list_assets(job.id)
    assert {a.asset_type for a in assets} == {"host", "endpoint", "secret"}
    assert any(a.asset_type == "endpoint" and a.value.endswith("/api/users") for a in assets)
    assert all(a.ai_label == "interesting" for a in assets)
    assert AWS_KEY not in ai.prompts[0]


def test_all_four_asset_types_for_one_job(db_session, program):
    svc = ReconService(
        db_session, FakeTool("subfinder", [sub("api.example.com")]),
        FakeTool("httpx", [host("https://api.example.com")]),
        fetcher_factory=lambda scope: FakeFetcher(), ai_provider_factory=lambda: FakeAI(),
    )
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)
    assert {a.asset_type for a in svc.list_assets(job.id)} == {
        "subdomain", "host", "endpoint", "secret"}


def test_triage_failure_does_not_fail_job(db_session, program):
    svc = full_service(db_session, ai=FakeAI(error=AIProviderError("upstream 500")))
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)
    db_session.refresh(job)
    assert job.status == "completed" and job.error is None
    assert job.notes == ["triage skipped: upstream 500"]


def test_unexpected_triage_error_and_no_provider_are_noted(db_session, program):
    svc = full_service(db_session, ai=FakeAI(error=RuntimeError("boom")))
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)
    db_session.refresh(job)
    assert job.status == "completed" and job.notes == ["triage failed: RuntimeError"]

    svc = full_service(db_session, ai=None)
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)
    db_session.refresh(job)
    assert job.status == "completed" and "No AI provider" in job.notes[0]
    assert len(svc.list_assets(job.id)) > 0


def test_http_fetcher_does_not_follow_out_of_scope_redirect(db_session, program):
    import httpx as httpx_lib

    requested = []

    def handler(request):
        requested.append(str(request.url))
        if request.url.host == "api.example.com":
            return httpx_lib.Response(302, headers={"location": "https://evil.com/x"})
        return httpx_lib.Response(200, text="pwned")

    client = httpx_lib.Client(transport=httpx_lib.MockTransport(handler))
    scope = ScopeValidator(program.scope_rules)
    fetcher = HttpFetcher(scope, client=client)
    assert fetcher("https://api.example.com/") is None
    assert requested == ["https://api.example.com/"]
