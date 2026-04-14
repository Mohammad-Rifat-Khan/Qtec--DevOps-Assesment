from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app, data_store


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def reset_app_state() -> Generator[None, Any, None]:
    global request_count, data_store
    request_count = 0
    data_store.clear()
    yield
    data_store.clear()


@pytest.fixture
def sample_data() -> dict:
    return {
        "message": "test message",
        "data": {
            "key1": "value1",
            "key2": 123,
        }
    }
