"""API integration tests — require DATABASE_URL pointing at Postgres+pgvector."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 with Postgres+Redis running",
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_signup_login_and_reject_bad_upload(client: TestClient, tmp_path: Path):
    email = "tester@example.com"
    password = "password123"
    signup = client.post(
        "/signup",
        json={"email": email, "password": password, "full_name": "Tester"},
    )
    assert signup.status_code in (201, 409)
    login = client.post("/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]

    bad = tmp_path / "x.exe"
    bad.write_bytes(b"MZ")
    res = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("x.exe", bad.read_bytes(), "application/octet-stream")},
    )
    assert res.status_code == 400
