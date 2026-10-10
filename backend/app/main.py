from fastapi import FastAPI

from app.api import recon

app = FastAPI(title="BountyHub")
app.include_router(recon.router)
