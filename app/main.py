"""
FastAPI application entry point.

Lifespan startup:
  - Creates all tables (idempotent via CREATE TABLE IF NOT EXISTS)
  - Seeds Chris and Donna if not already present
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, engine
from app.models import Base, User
from app.routers.api import router as api_router
from app.routers.health import router as health_router
from app.routers.web import configure_web_frontend
from app.routers.webhook import router as webhook_router
from app.routers.tasks import router as tasks_router


def _seed_users(db: Session) -> None:
    """Create Chris and Donna if they don't exist yet."""
    seed = [
        {"name": "Chris", "phone_number": settings.chris_phone},
        {"name": "Donna", "phone_number": settings.donna_phone},
    ]
    for data in seed:
        exists = db.query(User).filter(User.phone_number == data["phone_number"]).first()
        if not exists:
            db.add(User(**data))
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _seed_users(db)
    yield
    # Shutdown (nothing to do for now)


def create_app() -> FastAPI:
    app = FastAPI(title="Shopping Agent", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(webhook_router)
    app.include_router(tasks_router)
    configure_web_frontend(app, dist_dir=settings.web_dist_dir, shared_token=settings.web_shared_token)
    return app


app = create_app()
