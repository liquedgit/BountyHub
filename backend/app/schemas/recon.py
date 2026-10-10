from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReconScanCreate(BaseModel):
    program_id: int
    targets: list[str] = Field(min_length=1)


class ReconJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: int
    status: str
    current_stage: str | None
    targets: list[str]
    rejected_targets: list[str]
    error: str | None
    notes: list[str]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ReconAssetRead(BaseModel):
    """DB columns `asset_metadata` / `ai_score` are exposed as `meta` / `triage_score`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_type: str
    value: str
    source: str | None
    meta: dict = Field(validation_alias="asset_metadata")
    triage_score: float | None = Field(validation_alias="ai_score")
