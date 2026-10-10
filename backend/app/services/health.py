from redis import Redis

from app.repositories.health import HealthRepository
from app.schemas.health import HealthResponse


class HealthService:
    def __init__(self, repo: HealthRepository, redis: Redis) -> None:
        self._repo = repo
        self._redis = redis

    def check(self) -> HealthResponse:
        db_ok = self._repo.ping_database()
        try:
            redis_ok = bool(self._redis.ping())
        except Exception:
            redis_ok = False
        return HealthResponse(
            status="ok" if db_ok and redis_ok else "degraded",
            database="up" if db_ok else "down",
            redis="up" if redis_ok else "down",
        )
