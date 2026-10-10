from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.base import AIProviderError
from app.ai.factory import AIProviderFactory
from app.core.database import get_db
from app.repositories.recon_asset import ReconAssetRepository
from app.repositories.settings import SettingsRepository
from app.schemas.triage import TriageRequest, TriageResponse
from app.services.ai_triage import AITriageService

router = APIRouter(prefix="/triage", tags=["triage"])


def get_triage_service(db: Session = Depends(get_db)) -> AITriageService:
    try:
        provider = AIProviderFactory(SettingsRepository(db)).create()
    except AIProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return AITriageService(provider, ReconAssetRepository(db))


@router.post("", response_model=TriageResponse)
def run_triage(body: TriageRequest, service: AITriageService = Depends(get_triage_service)):
    try:
        assets = service.triage(job_id=body.job_id, asset_ids=body.asset_ids)
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return TriageResponse(provider=service.provider_name, assets=assets)
