import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import session as db_session
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Code reached outside FastAPI's DI (the websocket stream loop) looks up
    # `db_session.SessionLocal` fresh each call instead of importing it by
    # name, specifically so this swap reaches it too.
    original_session_local = db_session.SessionLocal
    db_session.SessionLocal = TestingSessionLocal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    db_session.SessionLocal = original_session_local
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def auth_headers(client):
    client.post("/api/v1/auth/signup", json={"email": "user@example.com", "password": "hunter22"})
    resp = client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "hunter22"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
