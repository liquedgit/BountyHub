import os

from arq.connections import RedisSettings

from app.db import SessionLocal
from app.repositories.recon import ReconRepository
from app.services.recon_service import ReconService


async def run_recon_job(ctx: dict, job_id: int) -> int:
    """ARQ task. Scope is re-checked inside ReconService.run_job."""
    with SessionLocal() as session:
        service = ReconService(ReconRepository(session))
        await service.run_job(job_id)
    return job_id


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))


class WorkerSettings:
    functions = [run_recon_job]
    redis_settings = redis_settings()
