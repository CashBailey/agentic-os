"""FastAPI app entrypoint. Bind 127.0.0.1:8000, no auth (single-user local)."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

log = logging.getLogger("agentos.backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic OS Backend",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url=None,
    )

    # CORS: localhost frontend dev only — never "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.CORS_ORIGIN],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    from app.api import (
        adapters,
        approvals,
        audit,
        auth_status,
        context,
        decisions,
        events,
        exports,
        health,
        memory,
        policies,
        projects,
        sessions,
        skills,
        workflows,
        worker as worker_router,
    )

    for r in (
        health.router,
        auth_status.router,
        projects.router,
        context.router,
        memory.router,
        decisions.router,
        sessions.router,
        adapters.router,
        policies.router,
        skills.router,
        workflows.router,
        approvals.router,
        audit.router,
        worker_router.router,
        exports.router,
        events.router,
    ):
        app.include_router(r)

    @app.on_event("startup")
    async def _startup() -> None:
        log.info(
            "Bound to %s:%d (no auth — single-user local)",
            settings.BIND_HOST,
            settings.BIND_PORT,
        )

    return app


app = create_app()


def run() -> None:
    """Convenience entrypoint: ``agentos-backend`` or ``python -m app.main``."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BIND_HOST,  # always 127.0.0.1
        port=settings.BIND_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    run()
