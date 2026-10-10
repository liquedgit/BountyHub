from fastapi import FastAPI

from app import models  # noqa: F401  (register tables)
from app.api.bounty import router as bounty_router

app = FastAPI(title="BountyHub")
app.include_router(bounty_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
