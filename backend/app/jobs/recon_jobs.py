import asyncio

from app.ai.factory import AIProviderFactory
from app.core.database import get_session_factory
from app.recon.fetcher import make_fetcher
from app.recon.httpx_tool import HttpxTool
from app.recon.subfinder import SubfinderTool
from app.repositories.settings import SettingsRepository
from app.services.recon import ReconService


def _run_sync(job_id: int) -> None:
    with get_session_factory()() as session:
        ReconService(
            session,
            SubfinderTool(),
            HttpxTool(),
            fetcher_factory=make_fetcher,
            ai_provider_factory=AIProviderFactory(SettingsRepository(session)).create,
        ).run_job(job_id)


async def run_recon_job(ctx: dict, job_id: int) -> int:
    """ARQ task: thin wrapper; scope is re-checked inside ReconService.run_job."""
    await asyncio.to_thread(_run_sync, job_id)
    return job_id
