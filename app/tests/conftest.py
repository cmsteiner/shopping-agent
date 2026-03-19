"""
Pytest fixtures for the shopping-agent test suite.

db fixture:
    In-memory SQLite session with all tables created and seeded with
    Chris (CHRIS_PHONE) and Donna (DONNA_PHONE).

client fixture:
    FastAPI TestClient using the db fixture via dependency override.
    The app lifespan is disabled so the test DB (in-memory) is used
    instead of the real DATABASE_URL path.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base, User
from app.routers.health import router as health_router


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db() -> Session:
    """Provide an in-memory SQLite session, freshly created for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Seed Chris and Donna
    for name, phone in [("Chris", settings.chris_phone), ("Donna", settings.donna_phone)]:
        if not session.query(User).filter(User.phone_number == phone).first():
            session.add(User(name=name, phone_number=phone))
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """
    FastAPI TestClient with the db session injected via dependency override.

    We build a minimal test app (no lifespan) that shares all routers from the
    main app, so the in-memory test DB is used instead of the real DB path.
    """
    test_app = FastAPI(title="Shopping Agent (Test)")
    test_app.include_router(health_router)

    def override_get_db():
        yield db

    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c
