"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.eventloop import ensure_compatible_event_loop
from app.core.logging import setup_logging
from app.db.session import dispose_engine

# Must run BEFORE uvicorn creates the event loop (Windows + psycopg async):
# module import happens before asyncio.run, lifespan would be too late.
ensure_compatible_event_loop()

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        _request: Request, exc: IntegrityError
    ) -> JSONResponse:
        logger.warning("Integrity conflict: %s", exc.orig)
        return JSONResponse(
            status_code=409, content={"detail": "Conflicto de integridad de datos"}
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
