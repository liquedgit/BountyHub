from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import factory as keys
from app.models.bounty import Finding, FindingStatus, Note, Program, Severity, Target
from app.models.recon_job import ReconJob
from app.repositories.settings import SettingsRepository
from app.schemas.dashboard import (
    DashboardSummary,
    FindingStats,
    RecentFinding,
    RecentScan,
    ScanStats,
)

RECENT_LIMIT = 5
_CLOSED = (FindingStatus.DUPLICATE, FindingStatus.REJECTED, FindingStatus.RESOLVED, FindingStatus.PAID)
_CREDENTIAL_KEY = {
    keys.PROVIDER_CLAUDE: keys.KEY_CLAUDE_TOKEN,
    keys.PROVIDER_OPENAI: keys.KEY_OPENAI_API_KEY,
}


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _count(self, model) -> int:
        return self._db.scalar(select(func.count()).select_from(model)) or 0

    def _group_counts(self, column) -> dict:
        return dict(self._db.execute(select(column, func.count()).group_by(column)).all())

    def _ai_configured(self) -> bool:
        repo = SettingsRepository(self._db)
        key = _CREDENTIAL_KEY.get(repo.get(keys.KEY_PROVIDER) or "")
        return key is not None and bool(repo.get(key))

    def summary(self) -> DashboardSummary:
        db = self._db
        by_status = self._group_counts(Finding.status)
        by_severity = self._group_counts(Finding.severity)
        payout = db.scalar(
            select(func.coalesce(func.sum(Finding.payout_cents), 0)).where(
                Finding.status == FindingStatus.PAID
            )
        )
        active = db.scalar(
            select(func.count()).select_from(ReconJob).where(
                ReconJob.status.in_(("queued", "running"))
            )
        )
        recent_findings = db.execute(
            select(Finding, Program.name)
            .join(Program, Program.id == Finding.program_id, isouter=True)
            .order_by(Finding.updated_at.desc(), Finding.id.desc())
            .limit(RECENT_LIMIT)
        ).all()
        recent_scans = db.execute(
            select(ReconJob, Program.name)
            .join(Program, Program.id == ReconJob.program_id, isouter=True)
            .order_by(ReconJob.id.desc())
            .limit(RECENT_LIMIT)
        ).all()
        return DashboardSummary(
            programs=self._count(Program),
            targets=self._count(Target),
            notes=self._count(Note),
            findings=FindingStats(
                total=sum(by_status.values()),
                open=sum(n for s, n in by_status.items() if s not in _CLOSED),
                by_status={s: by_status.get(s, 0) for s in FindingStatus},
                by_severity={s: by_severity.get(s, 0) for s in Severity},
            ),
            payout_cents_paid=int(payout or 0),
            scans=ScanStats(total=self._count(ReconJob), active=active or 0),
            ai_configured=self._ai_configured(),
            recent_findings=[
                RecentFinding(
                    id=f.id,
                    program_id=f.program_id,
                    program_name=name,
                    title=f.title,
                    severity=f.severity,
                    status=f.status,
                    updated_at=f.updated_at,
                )
                for f, name in recent_findings
            ],
            recent_scans=[
                RecentScan(
                    id=j.id,
                    program_id=j.program_id,
                    program_name=name,
                    status=j.status,
                    current_stage=j.current_stage,
                    target_count=len(j.targets or []),
                    created_at=j.created_at,
                    finished_at=j.finished_at,
                )
                for j, name in recent_scans
            ],
        )
