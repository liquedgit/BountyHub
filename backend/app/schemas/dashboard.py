from datetime import datetime

from pydantic import BaseModel

from app.models.bounty import FindingStatus, Severity


class FindingStats(BaseModel):
    total: int
    open: int
    by_status: dict[FindingStatus, int]
    by_severity: dict[Severity, int]


class ScanStats(BaseModel):
    total: int
    active: int


class RecentFinding(BaseModel):
    id: int
    program_id: int
    program_name: str | None
    title: str
    severity: Severity
    status: FindingStatus
    updated_at: datetime


class RecentScan(BaseModel):
    id: int
    program_id: int
    program_name: str | None
    status: str
    current_stage: str | None
    target_count: int
    created_at: datetime
    finished_at: datetime | None


class DashboardSummary(BaseModel):
    programs: int
    targets: int
    notes: int
    findings: FindingStats
    payout_cents_paid: int
    scans: ScanStats
    ai_configured: bool
    recent_findings: list[RecentFinding]
    recent_scans: list[RecentScan]
