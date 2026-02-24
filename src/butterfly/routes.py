"""HTTP routes for Butterfly."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from butterfly.config import settings
from butterfly.themes import THEMES, get_theme

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/api/sessions")
async def list_sessions(request: Request) -> JSONResponse:
    manager = request.app.state.session_manager
    sessions = []
    for sid, session in manager.sessions.items():
        sessions.append({
            "id": sid,
            "created": session.created.isoformat(),
            "clients": len(session.clients),
            "alive": session.alive,
        })
    return JSONResponse(sessions)


@router.get("/api/themes")
async def list_themes() -> JSONResponse:
    """List available themes with the current default."""
    return JSONResponse({
        "themes": list(THEMES.keys()),
        "current": settings.theme,
    })


@router.get("/api/themes/{name}")
async def get_theme_by_name(name: str) -> JSONResponse:
    """Get a specific theme's colors."""
    return JSONResponse(get_theme(name))


@router.get("/", response_class=HTMLResponse)
@router.get("/session/{session_id}", response_class=HTMLResponse)
async def index(request: Request, session_id: str | None = None) -> HTMLResponse:
    from pathlib import Path

    static_dir = Path(__file__).parent / "static"
    html = (static_dir / "index.html").read_text()
    return HTMLResponse(html)
