from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recon import ReconAsset, ReconJob
from app.models.scope import ScopeRule
from app.recon.base import ReconResult
from app.recon.scope import Rule


class ReconRepository:
    def __init__(self, session: Session):
        self.session = session

    def scope_rules(self, program_id: int) -> list[Rule]:
        rows = self.session.scalars(select(ScopeRule).where(ScopeRule.program_id == program_id))
        return [Rule(r.rule_type, r.pattern, r.in_scope) for r in rows]

    def create_job(self, program_id: int, targets: list[str], rejected: list[str]) -> ReconJob:
        job = ReconJob(program_id=program_id, targets=targets, rejected_targets=rejected)
        self.session.add(job)
        self.session.commit()
        return job

    def get_job(self, job_id: int) -> ReconJob | None:
        return self.session.get(ReconJob, job_id)

    def update_job(self, job: ReconJob, **fields) -> ReconJob:
        for key, value in fields.items():
            setattr(job, key, value)
        self.session.commit()
        return job

    def add_assets(self, job: ReconJob, results: list[ReconResult]) -> None:
        self.session.add_all(
            ReconAsset(job_id=job.id, asset_type=r.asset_type, value=r.value, source=r.source, meta=r.meta)
            for r in results
        )
        self.session.commit()

    def list_assets(self, job_id: int) -> list[ReconAsset]:
        return list(
            self.session.scalars(select(ReconAsset).where(ReconAsset.job_id == job_id).order_by(ReconAsset.id))
        )


def now() -> datetime:
    return datetime.now(timezone.utc)
