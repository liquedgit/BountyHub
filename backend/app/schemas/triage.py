from typing import Literal

from pydantic import BaseModel, Field

TriageLabel = Literal["likely_secret", "false_positive", "interesting", "routine"]


class TriageRequest(BaseModel):
    job_id: int | None = None
    asset_ids: list[int] | None = None


class TriagedAsset(BaseModel):
    id: int
    asset_type: str
    value: str
    score: float = Field(ge=0, le=100)
    label: TriageLabel
    reason: str


class TriageResponse(BaseModel):
    provider: str
    assets: list[TriagedAsset]
