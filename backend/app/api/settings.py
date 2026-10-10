from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.settings import SettingsRepository
from app.schemas.settings import AISettingsResponse, AISettingsUpdate
from app.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    return SettingsService(SettingsRepository(db))


@router.get("/ai", response_model=AISettingsResponse)
def get_ai_settings(service: SettingsService = Depends(get_settings_service)):
    return service.get_ai_settings()


@router.put("/ai", response_model=AISettingsResponse)
def update_ai_settings(
    body: AISettingsUpdate, service: SettingsService = Depends(get_settings_service)
):
    return service.update_ai_settings(body)
