import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, health, settings, triage
from app.api.bounty import router as bounty_router
from app.api.recon import router as recon_router
from app.core.config import get_settings
from app.jobs.queue import ArqJobQueue, JobQueue

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    owned: ArqJobQueue | None = None
    if getattr(app.state, "job_queue", None) is None:
        try:
            owned = await ArqJobQueue.create()
            app.state.job_queue = owned
        except Exception:  # noqa: BLE001 - API stays up; scans return 503
            logger.warning("could not create ARQ pool; recon scans unavailable")
    yield
    if owned is not None:
        await owned.close()


def create_app(job_queue: JobQueue | None = None) -> FastAPI:
    app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
    app.state.job_queue = job_queue
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(settings.router)
    app.include_router(triage.router)
    app.include_router(bounty_router)
    app.include_router(recon_router)
    return app


app = create_app()
