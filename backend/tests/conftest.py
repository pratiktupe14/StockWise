import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import Base, get_db
import app.models.entities  # Ensure all models are registered on Base.metadata
from app.main import app

# Isolated in-memory SQLite engine for fast, repeatable test suite execution
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


import app.core.database as core_db
core_db.SessionLocal = TestingSessionLocal
core_db.engine = test_engine
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes tables before each test and resets data cleanly after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def db_session():
    """Yields an isolated database session per test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    """Provides a FastAPI TestClient bound to the isolated test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
