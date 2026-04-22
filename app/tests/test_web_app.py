from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.web import configure_web_frontend


def _write_dist_files(tmp_path: Path) -> Path:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <head>
            <script type="module" src="/web-static/assets/app.js"></script>
          </head>
          <body>
            <div id="root"></div>
          </body>
        </html>
        """.strip(),
        encoding="utf-8",
    )
    (assets_dir / "app.js").write_text("console.log('hello');", encoding="utf-8")
    return dist_dir


def test_serves_index_html_for_valid_shared_link(tmp_path: Path):
    dist_dir = _write_dist_files(tmp_path)
    app = FastAPI()
    configure_web_frontend(app, dist_dir=dist_dir, shared_token="secret-token")

    with TestClient(app) as client:
        response = client.get("/app/secret-token")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/web-static/assets/app.js" in response.text


def test_serves_index_html_for_nested_spa_path(tmp_path: Path):
    dist_dir = _write_dist_files(tmp_path)
    app = FastAPI()
    configure_web_frontend(app, dist_dir=dist_dir, shared_token="secret-token")

    with TestClient(app) as client:
        response = client.get("/app/secret-token/list/current")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_rejects_invalid_shared_link_token(tmp_path: Path):
    dist_dir = _write_dist_files(tmp_path)
    app = FastAPI()
    configure_web_frontend(app, dist_dir=dist_dir, shared_token="secret-token")

    with TestClient(app) as client:
        response = client.get("/app/wrong-token")

    assert response.status_code == 403


def test_serves_built_frontend_assets(tmp_path: Path):
    dist_dir = _write_dist_files(tmp_path)
    app = FastAPI()
    configure_web_frontend(app, dist_dir=dist_dir, shared_token="secret-token")

    with TestClient(app) as client:
        response = client.get("/web-static/assets/app.js")

    assert response.status_code == 200
    assert "console.log('hello');" in response.text
