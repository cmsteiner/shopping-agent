from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles


def configure_web_frontend(app: FastAPI, *, dist_dir: str | Path, shared_token: str) -> None:
    dist_path = Path(dist_dir)
    assets_dir = dist_path / "assets"

    if assets_dir.exists():
        app.mount("/web-static", StaticFiles(directory=str(dist_path)), name="web-static")

    def _serve_index(token: str) -> FileResponse:
        if token != shared_token:
            raise HTTPException(status_code=403, detail="Invalid app token")
        index_path = dist_path / "index.html"
        if not index_path.exists():
            return PlainTextResponse("Web app build not found.", status_code=503)
        return FileResponse(index_path)

    @app.get("/app/{token}")
    def serve_web_app(token: str):
        return _serve_index(token)

    @app.get("/app/{token}/{full_path:path}")
    def serve_web_app_path(token: str, full_path: str):
        return _serve_index(token)
