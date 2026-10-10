import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import recon as recon_api
from app.db import get_session
from app.models.base import Base
from app.models.recon import JobStatus
from app.models.scope import ScopeRule
from app.recon.base import ToolError
from app.recon.httpx_tool import HttpxTool
from app.recon.scope import Rule, ScopeValidator
from app.recon.subfinder import SubfinderTool
from app.repositories.recon import ReconRepository
from app.services.recon_service import ReconService, ScopeViolation


class FakeRunner:
    """Stands in for the subprocess layer; records every command it is asked to run."""

    def __init__(self, outputs: dict[str, str]):
        self.outputs = outputs
        self.calls: list[tuple[list[str], str | None]] = []

    async def run(self, argv, stdin=None, timeout=600):
        self.calls.append((argv, stdin))
        return self.outputs[argv[0]] if argv[0] in self.outputs else self.outputs["*"]


class FailingRunner:
    async def run(self, argv, stdin=None, timeout=600):
        raise ToolError("boom")


@pytest.fixture
def session():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        s.add_all(
            [
                ScopeRule(program_id=1, rule_type="wildcard", pattern="*.example.com", in_scope=True),
                ScopeRule(program_id=1, rule_type="domain", pattern="example.com", in_scope=True),
                ScopeRule(program_id=1, rule_type="domain", pattern="admin.example.com", in_scope=False),
            ]
        )
        s.commit()
        yield s


SUBFINDER_OUT = "\n".join(
    json.dumps({"host": h, "input": "example.com"})
    for h in ["www.example.com", "admin.example.com", "api.example.com", "evil.other.net"]
)
HTTPX_OUT = "\n".join(
    json.dumps({"url": f"https://{h}", "input": h, "status_code": 200, "title": "T", "tech": ["nginx"]})
    for h in ["example.com", "www.example.com", "api.example.com"]
)


def make_service(session, sub_out=SUBFINDER_OUT, httpx_out=HTTPX_OUT):
    sub_runner = FakeRunner({"*": sub_out})
    httpx_runner = FakeRunner({"*": httpx_out})
    svc = ReconService(ReconRepository(session), SubfinderTool(sub_runner), HttpxTool(httpx_runner))
    return svc, sub_runner, httpx_runner


def test_scope_validator():
    v = ScopeValidator(
        [
            Rule("wildcard", "*.example.com"),
            Rule("domain", "admin.example.com", in_scope=False),
            Rule("ip", "10.0.0.0/24"),
            Rule("url", "https://app.test.io/login"),
        ]
    )
    assert v.is_in_scope("a.example.com")
    assert v.is_in_scope("https://a.example.com/x")
    assert not v.is_in_scope("example.com")  # wildcard doesn't cover the apex
    assert not v.is_in_scope("admin.example.com")
    assert not v.is_in_scope("notexample.com")
    assert v.is_in_scope("10.0.0.5") and not v.is_in_scope("10.0.1.5")
    assert v.is_in_scope("app.test.io")
    assert not ScopeValidator([]).is_in_scope("example.com")


def test_out_of_scope_targets_never_executed(session):
    svc, sub, hx = make_service(session)
    job = svc.create_job(1, ["example.com", "evil.com", "admin.example.com"])
    assert job.targets == ["example.com"]
    assert job.rejected_targets == ["evil.com", "admin.example.com"]
    asyncio.run(svc.run_job(job.id))
    assert [c[0][-1] for c in sub.calls] == ["example.com"]
    sent = hx.calls[0][1].split()
    assert sent == ["example.com", "www.example.com", "api.example.com"]
    assert "evil.other.net" not in sent and "admin.example.com" not in sent


def test_all_out_of_scope_rejected_without_any_subprocess(session):
    svc, sub, hx = make_service(session)
    with pytest.raises(ScopeViolation) as exc:
        svc.create_job(1, ["evil.com", "admin.example.com"])
    assert exc.value.rejected == ["evil.com", "admin.example.com"]
    assert sub.calls == [] and hx.calls == []


def test_run_revalidates_scope_server_side(session):
    svc, sub, hx = make_service(session)
    job = svc.create_job(1, ["example.com"])
    session.query(ScopeRule).filter_by(program_id=1).delete()  # scope revoked after queueing
    session.commit()
    asyncio.run(svc.run_job(job.id))
    assert job.status == JobStatus.FAILED
    assert sub.calls == [] and hx.calls == []


def test_pipeline_stores_assets_and_status(session):
    svc, _, _ = make_service(session)
    job = svc.create_job(1, ["example.com"])
    assert job.status == JobStatus.PENDING
    asyncio.run(svc.run_job(job.id))
    assert job.status == JobStatus.COMPLETED and job.finished_at
    assets = ReconRepository(session).list_assets(job.id)
    subs = {a.value for a in assets if a.asset_type == "subdomain"}
    hosts = {a.value for a in assets if a.asset_type == "host"}
    assert subs == {"www.example.com", "api.example.com"}
    assert hosts == {"https://example.com", "https://www.example.com", "https://api.example.com"}
    assert assets[-1].meta["status_code"] == 200


def test_tool_failure_marks_job_failed(session):
    svc = ReconService(ReconRepository(session), SubfinderTool(FailingRunner()), HttpxTool(FailingRunner()))
    job = svc.create_job(1, ["example.com"])
    asyncio.run(svc.run_job(job.id))
    assert job.status == JobStatus.FAILED and "boom" in job.error


def test_subfinder_parses_plain_lines():
    runner = FakeRunner({"*": "a.example.com\n\nB.Example.com.\n"})
    res = asyncio.run(SubfinderTool(runner).run(["example.com"]))
    assert [r.value for r in res] == ["a.example.com", "b.example.com"]
    assert runner.calls[0][0] == ["subfinder", "-silent", "-json", "-d", "example.com"]


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, function, *args):
        self.jobs.append((function, args))


def test_endpoints(session):
    app = FastAPI()
    app.include_router(recon_api.router)
    queue = FakeQueue()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[recon_api.get_queue] = lambda: queue
    c = TestClient(app)

    r = c.post("/recon/scans", json={"program_id": 1, "targets": ["evil.com"]})
    assert r.status_code == 422 and queue.jobs == []

    r = c.post("/recon/scans", json={"program_id": 1, "targets": ["example.com", "evil.com"]})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending" and body["rejected_targets"] == ["evil.com"]
    assert queue.jobs == [("run_recon_job", (body["id"],))]

    svc, _, _ = make_service(session)
    asyncio.run(svc.run_job(body["id"]))
    assert c.get(f"/recon/scans/{body['id']}").json()["status"] == "completed"
    assets = c.get(f"/recon/scans/{body['id']}/assets").json()
    assert {a["asset_type"] for a in assets} == {"subdomain", "host"}
    assert c.get("/recon/scans/999").status_code == 404
