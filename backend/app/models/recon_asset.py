from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReconAsset(Base):
    """A discovered subdomain/host/endpoint/secret, plus its AI triage result."""

    __tablename__ = "recon_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    asset_type: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[str] = mapped_column(Text)
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
