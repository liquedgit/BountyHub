import subprocess

import pytest

from app.models import ReconAsset, ReconJob
from app.recon.base import AssetType
from app.recon.httpx_tool import HttpxTool
from app.recon.runner import SubprocessRunner, ToolError
from app.recon.subfinder import SubfinderTool
from app.repositories.recon_asset import ReconAssetRepository
from app.repositories.recon_job import ReconJobRepository


class FakeRunner:
    def __init__(self, output="", error=None):
        self.output, self.error, self.calls = output, error, []

    def run(self, argv, stdin=None):
        self.calls.append((list(argv), stdin))
        if self.error:
            raise self.error
        return self.output


SUBFINDER_OUT = """api.example.com
WWW.example.com.
{"host":"dev.example.com","input":"example.com"}
api.example.com

not-json {
"""

HTTPX_OUT = "\n".join(
    [
        '{"url":"https://api.example.com","input":"api.example.com","status_code":200,'
        '"title":"API","tech":["nginx","Go"]}',
        "garbage",
        '{"url":"https://www.example.com","input":"www.example.com","status_code":404}',
        '{"url":"https://api.example.com","status_code":200}',
    ]
)


def test_subfinder_parses_and_dedupes():
    runner = FakeRunner(SUBFINDER_OUT)
    res = SubfinderTool(runner, binary="subfinder").run(["example.com"])
    assert [r.value for r in res] == [
        "api.example.com",
        "www.example.com",
        "dev.example.com",
    ]
    assert all(r.type is AssetType.SUBDOMAIN and r.source == "subfinder" for r in res)
    assert runner.calls[0][0] == ["subfinder", "-silent", "-d", "example.com"]


def test_subfinder_default_binary():
    assert SubfinderTool(FakeRunner()).binary == "subfinder"
    assert HttpxTool(FakeRunner()).binary == "pd-httpx"


def test_httpx_parses_json_lines():
    runner = FakeRunner(HTTPX_OUT)
    res = HttpxTool(runner).run(["api.example.com", "www.example.com"])
    assert [r.value for r in res] == ["https://api.example.com", "https://www.example.com"]
    assert res[0].type is AssetType.HOST
    assert res[0].metadata["status_code"] == 200
    assert res[0].metadata["title"] == "API"
    assert res[0].metadata["tech"] == ["nginx", "Go"]
    assert res[1].metadata["tech"] == []
    assert runner.calls[0][1] == "api.example.com\nwww.example.com\n"


def test_httpx_no_targets_skips_runner():
    runner = FakeRunner()
    assert HttpxTool(runner).run([]) == []
    assert runner.calls == []


def test_tool_errors_propagate():
    with pytest.raises(ToolError):
        SubfinderTool(FakeRunner(error=ToolError("tool not found: subfinder"))).run(["a.com"])
    with pytest.raises(ToolError):
        HttpxTool(FakeRunner(error=ToolError("timed out"))).run(["a.com"])


def test_subprocess_runner_missing_binary():
    with pytest.raises(ToolError, match="not found"):
        SubprocessRunner().run(["definitely-not-a-binary-xyz"])


def test_subprocess_runner_timeout_nonzero_and_no_shell(monkeypatch):
    seen = {}

    def fake_run(argv, **kw):
        seen.update(kw)
        if argv[0] == "slow":
            raise subprocess.TimeoutExpired(argv, kw["timeout"])
        return subprocess.CompletedProcess(argv, 2, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessRunner(timeout=3)
    with pytest.raises(ToolError, match="timed out"):
        runner.run(["slow"])
    with pytest.raises(ToolError, match="code 2: boom"):
        runner.run(["bad", "; rm -rf /"])
    assert seen["shell"] is False and seen["timeout"] == 3


def test_repositories(db_session):
    jobs = ReconJobRepository(db_session)
    job = jobs.create(program_id=1, targets=["a.example.com"], rejected_targets=["evil.com"])
    assert job.status == "queued" and job.rejected_targets == ["evil.com"]
    jobs.mark_running(job, "subfinder")
    assert job.started_at is not None and job.current_stage == "subfinder"

    results = SubfinderTool(FakeRunner("a.example.com\nb.example.com\n")).run(["example.com"])
    assets = ReconAssetRepository(db_session)
    added = assets.bulk_add(job.id, results)
    assert len(added) == 2
    listed = assets.list_by_job(job.id)
    assert [a.value for a in listed] == ["a.example.com", "b.example.com"]
    assert listed[0].source == "subfinder" and listed[0].ai_score is None
    assert assets.list_by_job(999) == []

    jobs.mark_finished(job)
    assert job.status == "completed" and job.finished_at is not None
    assert jobs.list_by_program(1) == [job]
    assert isinstance(db_session.get(ReconJob, job.id), ReconJob)
    assert isinstance(db_session.get(ReconAsset, listed[0].id), ReconAsset)
