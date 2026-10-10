from fastapi import FastAPI

from app.api import auth

app = FastAPI(title="BountyHub")
app.include_router(auth.router)
