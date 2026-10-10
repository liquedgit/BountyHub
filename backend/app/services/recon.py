import ipaddress
import logging
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.recon_job import ReconJob
from app.recon.base import ReconAssetResult, ReconTool
from app.recon.scope import ScopeValidator
from app.repositories.bounty import ProgramRepository, ScopeRuleRepository
from app.repositories.recon_asset import ReconAssetRepository
from app.repositories.recon_job import ReconJobRepository
from app.services.bounty import NotFoundError

logger = logging.getLogger(__name__)


class ScopeViolation(Exception):
    """None of the requested targets are in scope."""

    def __init__(self, rejected: list[str]):
        super().__init__("no requested target is in scope")
        self.rejected_targets = rejected


class ReconService:
    """Owns the recon pipeline order: scope -> subfinder -> httpx.

    Every tool input is filtered through a ScopeValidator built from the program's
    current rules; tool output is untrusted and re-validated before the next stage.
    """

    def __init__(self, db: Session, subfinder: ReconTool, httpx: ReconTool):
        self._programs = ProgramRepository(db)
        self._rules = ScopeRuleRepository(db)
        self._jobs = ReconJobRepository(db)
        self._assets = ReconAssetRepository(db)
        self._subfinder = subfinder
        self._httpx = httpx

    def _validator(self, program_id: int) -> ScopeValidator:
        return ScopeValidator(self._rules.list_for_program(program_id))

    def create_job(self, program_id: int, targets: Iterable[str]) -> ReconJob:
        if self._programs.get(program_id) is None:
            raise NotFoundError("program")
        requested = _dedupe(t.strip() for t in targets if t and t.strip())
        allowed, rejected = self._validator(program_id).partition(requested)
        if not allowed:
            raise ScopeViolation([d.target for d in rejected])
        return self._jobs.create(program_id, allowed, [d.target for d in rejected])

    def get_job(self, job_id: int) -> ReconJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError("scan")
        return job

    def list_assets(self, job_id: int):
        self.get_job(job_id)
        return self._assets.list_by_job(job_id)

    def run_job(self, job_id: int) -> None:
        """Run the pipeline; failures are recorded on the job, never raised."""
        job = self._jobs.get(job_id)
        if job is None:
            logger.warning("recon job %s not found", job_id)
            return
        try:
            self._run(job)
        except Exception as exc:  # noqa: BLE001 - job failure is data, not an exception
            logger.exception("recon job %s failed", job_id)
            self._jobs.mark_finished(job, error=f"{type(exc).__name__}: {exc}"[:1000])

    def _run(self, job: ReconJob) -> None:
        self._jobs.mark_running(job, "scope")
        validator = self._validator(job.program_id)
        allowed, newly_rejected = validator.partition(job.targets)
        rejected = _dedupe([*job.rejected_targets, *(d.target for d in newly_rejected)])
        job.rejected_targets = rejected
        if not allowed:
            self._jobs.mark_finished(job, error="no targets are in scope")
            return
        job.targets = list(allowed)

        self._jobs.set_stage(job, "subfinder")
        domains = [t for t in allowed if _is_bare_domain(t)]
        discovered = self._subfinder.run(domains) if domains else []
        keep, dropped = _split_in_scope(validator, discovered)
        job.rejected_targets = _dedupe([*job.rejected_targets, *dropped])
        self._assets.bulk_add(job.id, keep)

        self._jobs.set_stage(job, "httpx")
        probe_inputs = _dedupe([*allowed, *(r.value for r in keep)])
        probed = self._httpx.run(probe_inputs)
        probed_keep, probed_dropped = _split_in_scope(validator, probed)
        job.rejected_targets = _dedupe([*job.rejected_targets, *probed_dropped])
        self._assets.bulk_add(job.id, probed_keep)

        self._jobs.mark_finished(job)


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _is_bare_domain(target: str) -> bool:
    if "/" in target or ":" in target or "*" in target:
        return False
    try:
        ipaddress.ip_address(target)
    except ValueError:
        return True
    return False


def _split_in_scope(
    validator: ScopeValidator, results: list[ReconAssetResult]
) -> tuple[list[ReconAssetResult], list[str]]:
    keep: list[ReconAssetResult] = []
    dropped: list[str] = []
    for r in results:
        if validator.is_in_scope(r.value):
            keep.append(r)
        else:
            dropped.append(r.value)
    return keep, dropped
