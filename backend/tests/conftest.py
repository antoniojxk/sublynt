from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path("/tmp/sublynt-pytest")
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["SUBLYNT_DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["SUBLYNT_DATA_DIR"] = str(TEST_ROOT / "files")
os.environ["SUBLYNT_MAX_UPLOAD_BYTES"] = "1024"

from app.db.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    for path in (TEST_ROOT / "files").glob("*"):
        path.unlink()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
