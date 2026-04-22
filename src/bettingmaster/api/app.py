"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bettingmaster.config import settings
from bettingmaster.database import SessionLocal, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.info("Initializing database...")
    init_db()

    scheduler = None
    if settings.enable_scheduler:
        # Start scheduler (import here to avoid circular deps)
        from bettingmaster.scheduler import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
        logger.info("Scheduler started")

    yield

    # Shutdown
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

    app = FastAPI(
        title="BettingMaster",
        description="Slovak odds comparison API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.session_factory = SessionLocal

    from bettingmaster.api.routes.health import router as health_router
    from bettingmaster.api.routes.sports import router as sports_router
    from bettingmaster.api.routes.matches import router as matches_router
    from bettingmaster.api.routes.surebets import router as surebets_router
    from bettingmaster.api.routes.search import router as search_router
    from bettingmaster.api.routes.history import router as history_router
    from bettingmaster.api.routes.polymarket import router as polymarket_router
    from bettingmaster.api.routes.ws import router as ws_router

    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(sports_router, prefix="/api", tags=["sports"])
    app.include_router(matches_router, prefix="/api", tags=["matches"])
    app.include_router(surebets_router, prefix="/api", tags=["surebets"])
    app.include_router(search_router, prefix="/api", tags=["search"])
    app.include_router(history_router, prefix="/api", tags=["history"])
    app.include_router(polymarket_router, prefix="/api", tags=["polymarket"])
    app.include_router(ws_router, tags=["ws"])

    return app


app = create_app()
