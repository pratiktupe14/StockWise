import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Provides a FastAPI test client instance."""
    return TestClient(app)
