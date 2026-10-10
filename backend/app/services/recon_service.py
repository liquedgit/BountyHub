from app.models.recon import JobStatus, ReconJob
from app.recon.base import ReconResult, ReconTool
from app.recon.httpx_tool import HttpxTool
from app.recon.scope import ScopeValidator
from app.recon.subfinder import SubfinderTool
from app.repositories.recon import ReconRepository, now


class ScopeViolation(Exception):
    """Raised when none of the requested targets are in scope."""

    def __init__(self, rejected: list[str]):
        super().__init__("no requested target is in scope")
        self.rejected = rejected


class ReconService:
    """Runs Subfinder -> httpx. ScopeValidator gates every list of targets
    immediately before it is handed to a tool; the tools are never given
    unvalidated input."""

    def __init__(
        self,
        repo: ReconRepository,
        subfinder: ReconTool | None = None,
        httpx: ReconTool | None = None,
    ):
        self.repo = repo
        self.subfinder = subfinder or SubfinderTool()
        self.httpx = httpx or HttpxTool()

    def create_job(self, program_id: int, targets: list[str]) -> ReconJob:
        validator = ScopeValidator(self.repo.scope_rules(program_id))
        allowed, rejected = validator.partition(dict.fromkeys(t.strip() for t in targets if t.strip()))
        if not allowed:
            raise ScopeViolation(rejected)
        return self.repo.create_job(program_id, allowed, rejected)

    async def run_job(self, job_id: int) -> ReconJob:
        job = self.repo.get_job(job_id)
        if job is None:
            raise LookupError(f"recon job {job_id} not found")
        self.repo.update_job(job, status=JobStatus.RUNNING, started_at=now(), current_stage="scope")
        try:
            # Re-validate server-side: rules may have changed since the job was queued.
            validator = ScopeValidator(self.repo.scope_rules(job.program_id))
            roots, rejected = validator.partition(job.targets)
            if rejected:
                self.repo.update_job(job, rejected_targets=[*job.rejected_targets, *rejected])
            if not roots:
                raise ScopeViolation(rejected)

            self.repo.update_job(job, current_stage=self.subfinder.name)
            found = await self.subfinder.run(roots)
            # Discovered hosts are untrusted input too: filter before httpx sees them.
            discovered, dropped = validator.partition(r.value for r in found)
            if dropped:
                self.repo.update_job(job, rejected_targets=[*job.rejected_targets, *dropped])
            keep = set(discovered)
            self.repo.add_assets(job, [r for r in found if r.value in keep])

            hosts = list(dict.fromkeys([*roots, *discovered]))
            self.repo.update_job(job, current_stage=self.httpx.name)
            live: list[ReconResult] = await self.httpx.run(hosts)
            live_ok = [r for r in live if validator.is_in_scope(r.value)]
            self.repo.add_assets(job, live_ok)

            self.repo.update_job(job, status=JobStatus.COMPLETED, current_stage=None, finished_at=now())
        except Exception as exc:
            self.repo.update_job(job, status=JobStatus.FAILED, error=str(exc)[:1000], finished_at=now())
        return job
