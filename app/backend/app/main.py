import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.claude_usage import router as claude_usage_router
from app.programming_status import router as programming_status_router
from app.spotify import router as spotify_router
from app.system_health import router as system_health_router

app = FastAPI(title="Dashboard of My Life API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(system_health_router)
app.include_router(programming_status_router)
app.include_router(spotify_router)
app.include_router(claude_usage_router)


def _frontend_dist_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend_dist"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


frontend_dist = _frontend_dist_dir()
if frontend_dist.is_dir():
    assets_dir = str(frontend_dist / "assets")
    app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        # SPA fallback: any client-side route (e.g. /system-health) that isn't a
        # real file in dist/ still needs to resolve to index.html so React Router
        # can render it - StaticFiles(html=True) only handles directory requests,
        # not arbitrary deep links.
        candidate = frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")
else:

    @app.get("/")
    def root():
        return {"message": "Dashboard of My Life API is running"}