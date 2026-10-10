from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recon_asset import ReconAsset
from app.recon.base import ReconAssetResult


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

    def list_by_job(self, job_id: int) -> list[ReconAsset]:
        return self.list(job_id=job_id)

    def bulk_add(self, job_id: int, results: Sequence[ReconAssetResult]) -> list[ReconAsset]:
        assets = [
            ReconAsset(
                job_id=job_id,
                asset_type=r.type.value,
                value=r.value,
                source=r.source,
                asset_metadata=dict(r.metadata),
            )
            for r in results
        ]
        self._db.add_all(assets)
        self._db.commit()
        return assets

    def save_triage(self, results: dict[int, tuple[float, str, str]]) -> None:
        for asset in self.list(asset_ids=list(results)):
            asset.ai_score, asset.ai_label, asset.ai_reason = results[asset.id]
        self._db.commit()
