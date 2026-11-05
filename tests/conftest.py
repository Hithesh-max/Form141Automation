import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from apps.backend.app.database.config import Base, get_db
from apps.backend.app.database import models
from apps.backend.app.main import app


TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def reset_db():
    """Create fresh tables for every test and clean up afterwards."""
    Base.metadata.create_all(bind=test_engine)
    import apps.backend.app.database.config as db_config
    old_session_local = db_config.SessionLocal
    db_config.SessionLocal = TestingSessionLocal
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    db_config.SessionLocal = old_session_local
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    return TestClient(app)
