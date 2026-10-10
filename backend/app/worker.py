from arq.connections import RedisSettings

from app.core.config import get_settings
from app.jobs.recon_jobs import run_recon_job


async def ping(ctx: dict) -> str:
    return "pong"


class WorkerSettings:
    """ARQ worker settings; recon pipeline jobs are registered here in later tasks."""

    functions = [ping, run_recon_job]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
