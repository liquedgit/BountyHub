import ipaddress
import logging
from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIProviderError
from app.models.recon_job import ReconJob
from app.recon.base import AssetType, Fetcher, ReconAssetResult, ReconTool
from app.recon.js_crawler import JSEndpointCrawler
from app.recon.scope import ScopeValidator
from app.recon.secret_scanner import SecretScanner
from app.repositories.bounty import ProgramRepository, ScopeRuleRepository
from app.repositories.recon_asset import ReconAssetRepository
from app.repositories.recon_job import ReconJobRepository
from app.services.ai_triage import AITriageService
from app.services.bounty import NotFoundError

logger = logging.getLogger(__name__)


class ScopeViolation(Exception):
    """None of the requested targets are in scope."""

    def __init__(self, rejected: list[str]):
        super().__init__("no requested target is in scope")
        self.rejected_targets = rejected


class ReconService:
    """Owns the recon pipeline order: scope -> subfinder -> httpx -> js_crawler ->
    secret_scanner -> triage.

    Every tool input is filtered through a ScopeValidator built from the program's
    current rules; tool output is untrusted and re-validated before the next stage.
    """

    def __init__(
        self,
        db: Session,
        subfinder: ReconTool,
        httpx: ReconTool,
        fetcher_factory: Callable[[ScopeValidator], Fetcher] | None = None,
        ai_provider_factory: Callable[[], AIProvider] | None = None,
    ):
        self._programs = ProgramRepository(db)
        self._rules = ScopeRuleRepository(db)
        self._jobs = ReconJobRepository(db)
        self._assets = ReconAssetRepository(db)
        self._subfinder = subfinder
        self._httpx = httpx
        self._fetcher_factory = fetcher_factory
        self._ai_provider_factory = ai_provider_factory

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

        if self._fetcher_factory is not None:
            live = _dedupe(r.value for r in probed_keep if r.type == AssetType.HOST)
            fetcher = self._fetcher_factory(validator)
            for stage, tool_cls in (
                ("js_crawler", JSEndpointCrawler),
                ("secret_scanner", SecretScanner),
            ):
                self._jobs.set_stage(job, stage)
                found = tool_cls(validator, fetcher).run(live)
                # Secret values are redacted, so scope is judged by the fetched URL.
                self._assets.bulk_add(
                    job.id, [r for r in found if validator.is_in_scope(r.source)]
                )

        self._triage(job)
        self._jobs.mark_finished(job)

    def _triage(self, job: ReconJob) -> None:
        """Best-effort AI triage; any problem is noted on the job, never fails it."""
        self._jobs.set_stage(job, "triage")
        if self._ai_provider_factory is None:
            self._note(job, "triage skipped: no AI provider configured")
            return
        try:
            provider = self._ai_provider_factory()
            AITriageService(provider, self._assets).triage(job_id=job.id)
        except AIProviderError as exc:
            self._note(job, f"triage skipped: {exc}"[:500])
        except Exception as exc:  # noqa: BLE001 - triage must not fail the scan
            logger.warning("triage failed for recon job %s: %s", job.id, type(exc).__name__)
            self._note(job, f"triage failed: {type(exc).__name__}")

    def _note(self, job: ReconJob, text: str) -> None:
        job.notes = [*(job.notes or []), text]
        self._jobs.set_stage(job, "triage")  # commits the note


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
