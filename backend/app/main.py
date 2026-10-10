from fastapi import FastAPI

from app.api import health, settings, triage
from app.api.bounty import router as bounty_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name)
    app.include_router(health.router)
    app.include_router(bounty_router)
    app.include_router(settings.router)
    app.include_router(triage.router)
    return app


app = create_app()
