from fastapi import FastAPI

from app.api import auth, health
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name)
    app.include_router(health.router)
    app.include_router(auth.router)
    return app


app = create_app()
