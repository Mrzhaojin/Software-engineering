import os
import uuid

import pytest
from campus import create_app

TMP_ROOT = os.path.join(os.path.dirname(__file__), "_tmp")


@pytest.fixture
def app():
    os.makedirs(TMP_ROOT, exist_ok=True)
    db_path = os.path.join(TMP_ROOT, f"test-{uuid.uuid4().hex}.db")
    app = create_app({
        "TESTING": True,
        "DATABASE": db_path,
        "SECRET_KEY": "test",
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
