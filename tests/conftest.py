"""Pytest configuration and fixtures."""

from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app, data_store


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def reset_app_state() -> Generator[None, Any, None]:
    """Reset application state before each test."""
    global request_count, data_store
    request_count = 0
    data_store.clear()
    yield
    # Cleanup after test
    data_store.clear()


@pytest.fixture
def sample_data() -> dict:
    """Sample data for testing."""
    return {
        "message": "test message",
        "data": {
            "key1": "value1",
            "key2": 123,
        }
    }
