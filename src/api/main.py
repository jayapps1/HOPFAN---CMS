import logging
import asyncio
from contextlib import asynccontextmanager,suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.exceptions import register_exception_handlers
from src.api.middleware import AllowedHostMiddleware, RequestContextMiddleware, SafeErrorMiddleware, RequestBodyLimitMiddleware, logger
from src.api.v1.router import router
from src.config.online_settings import OnlineSettings


def create_app(settings: OnlineSettings | None = None) -> FastAPI:
    settings = settings or OnlineSettings.from_environment()
    # API_DEBUG controls only safe logging; HTTP traceback pages stay disabled.
    @asynccontextmanager
    async def lifespan(application):
        task=None
        if settings.sermon_scheduler_enabled:
            from src.services.sermon_scheduler import publication_loop
            task=asyncio.create_task(publication_loop())
        try:yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):await task
    application = FastAPI(
        title="HOPFAN API",
        lifespan=lifespan,
        description="House of Prayer for All Nations Church Management API",
        version="0.2.0",
        debug=False,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
        redirect_slashes=False,
    )
    application.state.settings = settings
    register_exception_handlers(application)
    application.include_router(router)
    # Last added runs first. Safe errors travel back through CORS and the
    # request/security headers. Host checks also cover preflight requests.
    application.add_middleware(SafeErrorMiddleware)
    application.add_middleware(RequestBodyLimitMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "X-Donation-Token", "Range"],
        expose_headers=["X-Request-ID", "Accept-Ranges", "Content-Range", "Content-Length", "Content-Disposition"],
    )
    application.add_middleware(AllowedHostMiddleware, allowed_hosts=settings.api_allowed_hosts)
    application.add_middleware(RequestContextMiddleware)
    logger.setLevel(logging.DEBUG if settings.api_debug else logging.INFO)
    # Alembic's logging setup can disable pre-existing named loggers in a
    # shared process. A newly created API must restore its safe request logger.
    logger.disabled = False
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s hopfan.api %(message)s"))
        logger.addHandler(handler)
    # No schema creation, migrations, seeding, or desktop imports on startup.
    return application


app = create_app()
