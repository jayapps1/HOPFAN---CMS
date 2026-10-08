"""Small idempotent publication scheduler; no transcoding on request threads."""
import asyncio
from contextlib import suppress
from starlette.concurrency import run_in_threadpool

def publish_scheduled():
    from src.config.database import SessionLocal
    from src.services.sermon_service import SermonService
    from src.services.api_readiness_service import check_api_database_access
    with SessionLocal() as db:
        check_api_database_access(db)
        return SermonService.publish_due(db)

async def publication_loop():
    from src.api.middleware import logger
    while True:
        await asyncio.sleep(30)
        try:await run_in_threadpool(publish_scheduled)
        except Exception:logger.warning('Scheduled sermon publication is temporarily unavailable.')
