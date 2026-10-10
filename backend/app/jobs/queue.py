from typing import Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings


class JobQueue(Protocol):
    async def enqueue_recon_job(self, job_id: int) -> None: ...


class ArqJobQueue:
    def __init__(self, pool: ArqRedis):
        self._pool = pool

    @classmethod
    async def create(cls) -> "ArqJobQueue":
        dsn = RedisSettings.from_dsn(get_settings().redis_url)
        dsn.conn_retries = 0
        return cls(await create_pool(dsn))

    async def enqueue_recon_job(self, job_id: int) -> None:
        await self._pool.enqueue_job("run_recon_job", job_id)

    async def close(self) -> None:
        await self._pool.aclose()
