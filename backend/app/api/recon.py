from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.jobs.queue import JobQueue
from app.recon.httpx_tool import HttpxTool
from app.recon.subfinder import SubfinderTool
from app.repositories.recon_job import ReconJobRepository
from app.schemas.recon import ReconAssetRead, ReconJobRead, ReconScanCreate
from app.services.bounty import NotFoundError
from app.services.recon import ReconService, ScopeViolation

router = APIRouter(
    prefix="/recon/scans", tags=["recon"], dependencies=[Depends(get_current_user)]
)


def get_job_queue(request: Request) -> JobQueue | None:
    return getattr(request.app.state, "job_queue", None)


def get_recon_service(db: Session = Depends(get_db)) -> ReconService:
    return ReconService(db, SubfinderTool(), HttpxTool())


@router.post("", response_model=ReconJobRead, status_code=status.HTTP_202_ACCEPTED)
async def create_scan(
    body: ReconScanCreate,
    service: ReconService = Depends(get_recon_service),
    queue: JobQueue | None = Depends(get_job_queue),
    db: Session = Depends(get_db),
):
    try:
        job = service.create_job(body.program_id, body.targets)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except ScopeViolation as e:
        return JSONResponse(
            status_code=422,
            content={"detail": str(e), "rejected_targets": e.rejected_targets},
        )
    # Checked after scope and the network guard so a refused target is a 422 either way.
    if queue is None:
        ReconJobRepository(db).mark_finished(job, error="could not enqueue job")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "job queue unavailable")
    try:
        await queue.enqueue_recon_job(job.id)
    except Exception as e:  # noqa: BLE001
        ReconJobRepository(db).mark_finished(job, error="could not enqueue job")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "job queue unavailable") from e
    return job


@router.get("", response_model=list[ReconJobRead])
def list_scans(
    program_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    service: ReconService = Depends(get_recon_service),
):
    return service.list_jobs(program_id=program_id, limit=limit)


@router.get("/{job_id}", response_model=ReconJobRead)
def get_scan(job_id: int, service: ReconService = Depends(get_recon_service)):
    try:
        return service.get_job(job_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e


@router.get("/{job_id}/assets", response_model=list[ReconAssetRead])
def get_scan_assets(job_id: int, service: ReconService = Depends(get_recon_service)):
    try:
        return service.list_assets(job_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
