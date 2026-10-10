from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recon_job import ReconJob


class ReconJobRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        program_id: int,
        targets: Sequence[str],
        rejected_targets: Sequence[str] = (),
    ) -> ReconJob:
        job = ReconJob(
            program_id=program_id,
            status="queued",
            targets=list(targets),
            rejected_targets=list(rejected_targets),
        )
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def get(self, job_id: int) -> ReconJob | None:
        return self._db.get(ReconJob, job_id)

    def list_by_program(self, program_id: int) -> list[ReconJob]:
        stmt = (
            select(ReconJob)
            .where(ReconJob.program_id == program_id)
            .order_by(ReconJob.id.desc())
        )
        return list(self._db.scalars(stmt))

    def mark_running(self, job: ReconJob, stage: str | None = None) -> ReconJob:
        job.status = "running"
        job.current_stage = stage
        if job.started_at is None:
            job.started_at = datetime.now(UTC)
        self._db.commit()
        return job

    def set_stage(self, job: ReconJob, stage: str) -> ReconJob:
        job.current_stage = stage
        self._db.commit()
        return job

    def mark_finished(self, job: ReconJob, error: str | None = None) -> ReconJob:
        job.status = "failed" if error else "completed"
        job.error = error
        job.current_stage = None
        job.finished_at = datetime.now(UTC)
        self._db.commit()
        return job
