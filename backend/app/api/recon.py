from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.repositories.recon import ReconRepository
from app.schemas.recon import ReconAssetOut, ReconJobOut, ReconScanRequest
from app.services.recon_service import ReconService, ScopeViolation

router = APIRouter(prefix="/recon", tags=["recon"])


class JobQueue(Protocol):
    async def enqueue_job(self, function: str, *args) -> object: ...


def get_queue(request: Request) -> JobQueue:
    queue = getattr(request.app.state, "arq_pool", None)
    if queue is None:
        raise HTTPException(503, "job queue unavailable")
    return queue


def get_repo(session: Session = Depends(get_session)) -> ReconRepository:
    return ReconRepository(session)


@router.post("/scans", response_model=ReconJobOut, status_code=202)
async def start_scan(
    body: ReconScanRequest,
    repo: ReconRepository = Depends(get_repo),
    queue: JobQueue = Depends(get_queue),
):
    try:
        job = ReconService(repo).create_job(body.program_id, body.targets)
    except ScopeViolation as exc:
        raise HTTPException(422, {"detail": "no targets in scope", "rejected_targets": exc.rejected})
    await queue.enqueue_job("run_recon_job", job.id)
    return job


@router.get("/scans/{job_id}", response_model=ReconJobOut)
def get_scan(job_id: int, repo: ReconRepository = Depends(get_repo)):
    job = repo.get_job(job_id)
    if job is None:
        raise HTTPException(404, "scan not found")
    return job


@router.get("/scans/{job_id}/assets", response_model=list[ReconAssetOut])
def get_scan_assets(job_id: int, repo: ReconRepository = Depends(get_repo)):
    if repo.get_job(job_id) is None:
        raise HTTPException(404, "scan not found")
    return repo.list_assets(job_id)
