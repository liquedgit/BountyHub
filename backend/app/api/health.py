from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis import get_redis
from app.repositories.health import HealthRepository
from app.schemas.health import HealthResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


def get_health_service(
    db: Session = Depends(get_db), redis: Redis = Depends(get_redis)
) -> HealthService:
    return HealthService(HealthRepository(db), redis)


@router.get("/health", response_model=HealthResponse)
def health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return service.check()
