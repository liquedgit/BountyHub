import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ScopeAction(str, enum.Enum):
    IN = "in"
    OUT = "out"


class ScopeType(str, enum.Enum):
    DOMAIN = "domain"
    WILDCARD = "wildcard"
    IP = "ip"
    URL = "url"


class FindingStatus(str, enum.Enum):
    NEW = "new"
    TRIAGED = "triaged"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    RESOLVED = "resolved"
    PAID = "paid"


class Severity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Program(TimestampMixin, Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(500))
    reward_info: Mapped[str | None] = mapped_column(Text)

    scope_rules: Mapped[list["ScopeRule"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="ScopeRule.id"
    )
    targets: Mapped[list["Target"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="Target.id"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="Finding.id"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="Note.id"
    )


class ScopeRule(Base):
    __tablename__ = "scope_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    action: Mapped[ScopeAction] = mapped_column(Enum(ScopeAction, values_callable=lambda e: [m.value for m in e]))
    type: Mapped[ScopeType] = mapped_column(Enum(ScopeType, values_callable=lambda e: [m.value for m in e]))
    value: Mapped[str] = mapped_column(String(500))

    program: Mapped[Program] = relationship(back_populates="scope_rules")


class Target(TimestampMixin, Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    program: Mapped[Program] = relationship(back_populates="targets")


class Finding(TimestampMixin, Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[int | None] = mapped_column(ForeignKey("targets.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, values_callable=lambda e: [m.value for m in e]), default=FindingStatus.NEW
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, values_callable=lambda e: [m.value for m in e]), default=Severity.INFO
    )
    payout_cents: Mapped[int | None] = mapped_column(Integer)

    program: Mapped[Program] = relationship(back_populates="findings")
    notes: Mapped[list["Note"]] = relationship(back_populates="finding", cascade="all, delete-orphan")


class Note(TimestampMixin, Base):
    """Markdown note attached to a program and optionally to one of its findings."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    body_md: Mapped[str] = mapped_column(Text, default="")

    program: Mapped[Program] = relationship(back_populates="notes")
    finding: Mapped[Finding | None] = relationship(back_populates="notes")
