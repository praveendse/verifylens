"""Serve the built React app from FastAPI (same origin as the API)."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist: Path) -> bool:
    """Serve `dist` at "/". Returns False (and serves nothing) if not built.

    Must be called after all API routers are registered, so API routes win.
    """
    index = dist / "index.html"
    if not index.is_file():
        return False

    dist = dist.resolve()

    # Vite puts hashed JS/CSS/images here; safe to cache for a long time.
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # Unknown API paths must stay JSON 404s, not return the HTML page.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        # Top-level files from public/ (favicon etc.), never outside dist.
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)

        # index.html must not be cached, so a new deploy is picked up at once.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True
