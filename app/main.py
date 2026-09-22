"""The application factory: middleware order, routes and static files.

Middleware is listed outermost first, so a request id exists before
anything can fail, and the security headers are attached to whatever
answer comes back, including a problem response.

There is no module-level application: importing this module must not
build a client or read the environment. Uvicorn is pointed at the factory
(``uvicorn app.main:create_app --factory``).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.adapters.llm import LLMPort
from app.api import problems, routes
from app.api.dependencies import SERVICES_STATE_KEY, build_services, get_settings
from app.config import Settings
from app.observability import configure_logging
from app.security.body_size import BodySizeLimitMiddleware
from app.security.headers import SecurityHeadersMiddleware
from app.security.rate_limit import RateLimitMiddleware
from app.security.request_id import RequestIdMiddleware
from app.version import VERSION

API_PREFIX = "/api/v1"
WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
GZIP_MINIMUM_SIZE = 1024

TITLE = "Mohlat"
DESCRIPTION = (
    "Understand a legal notice and the date you need to act by. Information, not legal advice."
)

_STATIC_MOUNTS = ("css", "js", "i18n", "samples")


def create_app(settings: Settings | None = None, llm: LLMPort | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Configuration to use instead of reading the environment.
        llm: A model client to use instead of the real one, for tests.

    Returns:
        The configured application.
    """
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved.log_level)

    is_prod = resolved.app_env == "prod"
    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=VERSION,
        docs_url=None if is_prod else "/api/docs",
        redoc_url=None if is_prod else "/api/redoc",
        openapi_url="/api/openapi.json",
    )

    services = build_services(resolved, llm=llm)
    setattr(app.state, SERVICES_STATE_KEY, services)

    # Added last runs first, so this list reads innermost to outermost.
    app.add_middleware(
        BaseHTTPMiddleware,
        dispatch=BodySizeLimitMiddleware(app, resolved).__call__,
    )
    app.add_middleware(
        BaseHTTPMiddleware,
        dispatch=RateLimitMiddleware(app, resolved, services.limiter).__call__,
    )
    app.add_middleware(GZipMiddleware, minimum_size=GZIP_MINIMUM_SIZE)
    app.add_middleware(BaseHTTPMiddleware, dispatch=SecurityHeadersMiddleware(app).__call__)
    app.add_middleware(BaseHTTPMiddleware, dispatch=RequestIdMiddleware(app).__call__)

    problems.install(app)
    app.include_router(routes.router, prefix=API_PREFIX)
    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    """Serve the page and its assets, if the web directory is present."""
    if not WEB_ROOT.is_dir():  # pragma: no cover - only in a stripped image
        return

    for name in _STATIC_MOUNTS:
        directory = WEB_ROOT / name
        if directory.is_dir():
            app.mount(f"/{name}", StaticFiles(directory=directory), name=name)

    index = WEB_ROOT / "index.html"

    @app.get("/", include_in_schema=False)
    async def page() -> FileResponse:
        """Serve the single page."""
        return FileResponse(index, media_type="text/html")
