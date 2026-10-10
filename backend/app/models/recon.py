from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconJob(Base):
    __tablename__ = "recon_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.PENDING)
    targets: Mapped[list] = mapped_column(JSON, default=list)
    rejected_targets: Mapped[list] = mapped_column(JSON, default=list)
    current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assets: Mapped[list["ReconAsset"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class ReconAsset(Base):
    """A discovered subdomain/host/endpoint/secret. Metadata is tool-specific."""

    __tablename__ = "recon_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("recon_jobs.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(16))  # subdomain | host | endpoint | secret
    value: Mapped[str] = mapped_column(String(2048))
    source: Mapped[str] = mapped_column(String(32))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    triage_score: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    job: Mapped[ReconJob] = relationship(back_populates="assets")
