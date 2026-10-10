from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReconScanRequest(BaseModel):
    program_id: int
    targets: list[str] = Field(min_length=1)


class ReconJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: int
    status: str
    current_stage: str | None
    targets: list[str]
    rejected_targets: list[str]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ReconAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_type: str
    value: str
    source: str
    meta: dict
    triage_score: float | None
