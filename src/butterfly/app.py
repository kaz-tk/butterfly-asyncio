"""FastAPI application factory with lifespan."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from butterfly.config import settings
from butterfly.routes import router
from butterfly.session import SessionManager
from butterfly.websocket import ws_router

logger = logging.getLogger("butterfly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    manager = SessionManager()
    app.state.session_manager = manager
    logger.info("Butterfly started on %s:%d", settings.host, settings.port)
    yield
    await manager.shutdown()
    logger.info("Butterfly stopped")


app = FastAPI(
    title="Butterfly",
    version="4.0.0",
    lifespan=lifespan,
    root_path=settings.uri_root_path,
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(router)
app.include_router(ws_router)
