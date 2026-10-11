from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import create_app
from app.models import Program, ReconJob, ScopeRule
from app.recon.base import AssetType, ReconAssetResult, ReconTool
from app.recon.fetcher import HttpFetcher
from app.recon.netguard import NetworkGuard, SystemResolver
from app.recon.scope import ScopeValidator
from app.services.recon import ReconService, ScopeViolation

PUBLIC = "93.184.216.34"
BLOCKED = [
    "127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1",
    "0.0.0.0", "224.0.0.1", "240.0.0.1", "[::1]", "::1", "fd00::1", "fe80::1", "[::ffff:10.0.0.5]",
    "::ffff:127.0.0.1", "http://169.254.169.254/latest/meta-data", "10.0.0.5:8080", "2130706433",
    "0x7f.1", "localhost", "LOCALHOST", "backend", "postgres", "redis", "http://backend:8000/",
    "printer.local", "db.internal", "app.localhost", "nas.lan", "router.home.arpa",
]


class FakeResolver:
    def __init__(self, table=None):
        self.table, self.calls = table or {}, []

    def resolve(self, host):
        self.calls.append(host)
        return self.table.get(host, [])


class FakeTool(ReconTool):
    def __init__(self, name, results=()):
        self.name, self.results, self.calls = name, list(results), []

    def run(self, targets):
        self.calls.append(list(targets))
        return list(self.results)


def guard(table=None, allow_private=False):
    return NetworkGuard(FakeResolver(table), allow_private)


@pytest.mark.parametrize("value", BLOCKED)
def test_check_target_blocks(value):
    d = guard().check_target(value)
    assert not d and d.reason.startswith("blocked: private or internal address")


@pytest.mark.parametrize(
    "value", ["example.com", "https://app.example.com/x", "93.184.216.34", "[2606:4700::1]",
              "8.8.8.8:53", "xn--e1afmkfd.xn--p1ai"]
)
def test_check_target_allows_public(value):
    assert guard().check_target(value)


def test_check_resolved_any_private_address_blocks():
    g = guard({"a.example.com": [PUBLIC, "10.0.0.5"], "b.example.com": [PUBLIC],
               "c.example.com": ["::ffff:127.0.0.1"]})
    assert not g.check_resolved("a.example.com")
    assert g.check_resolved("b.example.com")
    assert not g.check_resolved("c.example.com")
    assert g.check_resolved("unresolvable.example.com")  # left to the tool


def test_resolver_failure_is_unresolved():
    class Boom:
        def resolve(self, host):
            raise OSError("nope")

    assert NetworkGuard(Boom()).check_resolved("x.example.com")


def test_allow_private_turns_guard_off():
    g = guard({"x.example.com": ["10.0.0.5"]}, allow_private=True)
    assert all(g.check(v) for v in BLOCKED)
    assert g.check("x.example.com")
    assert g._resolver.calls == []


def test_system_resolver_times_out(monkeypatch):
    import socket
    import time

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: time.sleep(1))
    assert SystemResolver(timeout=0.05).resolve("slow.example.com") == []


# --- service ---------------------------------------------------------------


@pytest.fixture
def program(db_session):
    p = Program(name="P")
    p.scope_rules = [
        ScopeRule(action="in", type="wildcard", value="*.example.com"),
        ScopeRule(action="in", type="domain", value="example.com"),
        ScopeRule(action="in", type="ip", value="0.0.0.0/0"),
        ScopeRule(action="in", type="ip", value="::/0"),
        ScopeRule(action="in", type="domain", value="localhost"),
        ScopeRule(action="in", type="domain", value="backend"),
        ScopeRule(action="in", type="domain", value="postgres"),
        ScopeRule(action="in", type="domain", value="redis"),
        ScopeRule(action="in", type="domain", value="printer.local"),
    ]
    db_session.add(p)
    db_session.commit()
    return p


def make_service(db, guard_, subfinder=None, httpx_tool=None, fetcher=None):
    return ReconService(
        db, subfinder or FakeTool("subfinder"), httpx_tool or FakeTool("httpx"),
        fetcher_factory=(lambda scope: fetcher) if fetcher else None, guard=guard_,
    )


@pytest.mark.parametrize(
    "target", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "[::1]", "localhost", "backend",
              "postgres", "redis", "printer.local"],
)
def test_blocked_target_rejected_although_in_scope(db_session, program, target):
    subfinder, httpx_tool = FakeTool("subfinder"), FakeTool("httpx")
    svc = make_service(db_session, guard(), subfinder, httpx_tool)
    with pytest.raises(ScopeViolation) as exc:
        svc.create_job(program.id, [target])
    assert len(exc.value.rejected_targets) == 1
    assert exc.value.rejected_targets[0].startswith("blocked: private or internal address")
    assert target in exc.value.rejected_targets[0]
    assert subfinder.calls == [] and httpx_tool.calls == []
    assert db_session.query(ReconJob).count() == 0


def test_blocked_target_dropped_public_kept(db_session, program):
    svc = make_service(db_session, guard({"example.com": [PUBLIC]}))
    job = svc.create_job(program.id, ["example.com", "10.0.0.5", "evil.com"])
    assert job.targets == ["example.com"]
    assert job.rejected_targets[0] == "evil.com"
    assert job.rejected_targets[1].startswith("blocked: private or internal address")


def test_public_name_resolving_private_dropped_before_httpx(db_session, program):
    httpx_tool = FakeTool("httpx")
    svc = make_service(db_session, guard({"example.com": [PUBLIC],
                                          "api.example.com": ["10.0.0.5"]}),
                       FakeTool("subfinder", [ReconAssetResult(
                           AssetType.SUBDOMAIN, "api.example.com", "subfinder")]), httpx_tool)
    job = svc.create_job(program.id, ["example.com"])
    svc.run_job(job.id)
    db_session.refresh(job)
    assert httpx_tool.calls == [["example.com"]]
    assert any(r.startswith("blocked: private or internal address") and "api.example.com" in r
               for r in job.rejected_targets)
    assert [a.value for a in svc.list_assets(job.id)] == []


def test_mixed_public_private_name_dropped(db_session, program):
    svc = make_service(db_session, guard({"example.com": [PUBLIC, "192.168.0.9"]}))
    with pytest.raises(ScopeViolation) as exc:
        svc.create_job(program.id, ["example.com"])
    assert exc.value.rejected_targets[0].startswith("blocked: private or internal address")


def test_guard_rechecked_at_run_time(db_session, program):
    table = {"example.com": [PUBLIC]}
    httpx_tool = FakeTool("httpx")
    svc = make_service(db_session, guard(table), httpx_tool=httpx_tool)
    job = svc.create_job(program.id, ["example.com"])
    table["example.com"] = ["10.0.0.5"]  # DNS changed after submission
    svc.run_job(job.id)
    db_session.refresh(job)
    assert httpx_tool.calls == []
    assert job.status == "failed"
    assert any(r.startswith("blocked: private") for r in job.rejected_targets)


def test_private_live_host_not_fetched(db_session, program):
    class Fetcher:
        calls = []

        def __call__(self, url):
            self.calls.append(url)

    fetcher = Fetcher()
    g = guard({"example.com": [PUBLIC], "api.example.com": [PUBLIC]})
    httpx_tool = FakeTool("httpx", [
        ReconAssetResult(AssetType.HOST, "https://api.example.com", "httpx"),
    ])
    svc = make_service(db_session, g, httpx_tool=httpx_tool, fetcher=fetcher)
    job = svc.create_job(program.id, ["example.com"])
    g._resolver.table["api.example.com"] = ["127.0.0.1"]  # rebinds before the crawl
    svc.run_job(job.id)
    assert fetcher.calls == []


def test_flag_off_allows_private(db_session, program):
    svc = make_service(db_session, guard(allow_private=True))
    job = svc.create_job(program.id, ["10.0.0.5", "localhost"])
    assert job.targets == ["10.0.0.5", "localhost"]


def test_post_scan_blocked_target_422(db_session, program):
    class Q:
        jobs = []

        async def enqueue_recon_job(self, job_id):
            self.jobs.append(job_id)

    app = create_app(job_queue=Q())
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: object()
    from app.api.recon import get_recon_service

    app.dependency_overrides[get_recon_service] = lambda: make_service(db_session, guard())
    with TestClient(app) as c:
        r = c.post("/recon/scans", json={"program_id": program.id,
                                         "targets": ["169.254.169.254", "backend"]})
    assert r.status_code == 422
    assert all(t.startswith("blocked: private or internal address")
               for t in r.json()["rejected_targets"])
    assert len(r.json()["rejected_targets"]) == 2
    assert Q.jobs == []


# --- fetcher ---------------------------------------------------------------


def fetcher(handler, g):
    scope = ScopeValidator([SimpleNamespace(action="in", type="wildcard", value="*.example.com"),
                            SimpleNamespace(action="in", type="ip", value="127.0.0.0/8")])
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpFetcher(scope, client=client, guard=g)


def test_fetcher_redirect_to_loopback_not_followed():
    seen = []

    def h(r):
        seen.append(str(r.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    f = fetcher(h, guard({"app.example.com": [PUBLIC]}))
    assert f("https://app.example.com/") is None
    assert seen == ["https://app.example.com/"]


def test_fetcher_redirect_to_name_resolving_private_not_followed():
    seen = []

    def h(r):
        seen.append(str(r.url))
        return httpx.Response(302, headers={"location": "https://intranet.example.com/"})

    g = guard({"app.example.com": [PUBLIC], "intranet.example.com": ["10.1.1.1"]})
    assert fetcher(h, g)("https://app.example.com/") is None
    assert seen == ["https://app.example.com/"]


def test_fetcher_first_url_guarded_and_public_works():
    seen = []

    def h(r):
        seen.append(str(r.url))
        return httpx.Response(200, text="ok")

    g = guard({"app.example.com": [PUBLIC], "db.example.com": ["10.0.0.5"]})
    f = fetcher(h, g)
    assert f("http://127.0.0.1/") is None
    assert f("https://db.example.com/") is None
    assert seen == []
    assert f("https://app.example.com/") == "ok"
    assert fetcher(h, guard({"x.example.com": ["10.0.0.5"]}, allow_private=True))(
        "https://x.example.com/") == "ok"
