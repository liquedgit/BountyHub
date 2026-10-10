from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recon_asset import ReconAsset


class ReconAssetRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list(
        self, job_id: int | None = None, asset_ids: Sequence[int] | None = None
    ) -> list[ReconAsset]:
        stmt = select(ReconAsset).order_by(ReconAsset.id)
        if job_id is not None:
            stmt = stmt.where(ReconAsset.job_id == job_id)
        if asset_ids:
            stmt = stmt.where(ReconAsset.id.in_(asset_ids))
        return list(self._db.scalars(stmt))

    def save_triage(self, results: dict[int, tuple[float, str, str]]) -> None:
        for asset in self.list(asset_ids=list(results)):
            asset.ai_score, asset.ai_label, asset.ai_reason = results[asset.id]
        self._db.commit()
