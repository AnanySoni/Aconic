"""Pure unit tests that do not require Postgres/Redis."""

from pathlib import Path

import pytest
from fastapi import HTTPException


def test_validate_upload_rejects_exe(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "10485760")
    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.services.storage import validate_upload

    class FakeFile:
        filename = "malware.exe"
        content_type = "application/octet-stream"

    with pytest.raises(HTTPException) as exc:
        validate_upload(FakeFile(), 100)  # type: ignore[arg-type]
    assert exc.value.status_code == 400
    assert "Unsupported" in exc.value.detail


def test_validate_upload_accepts_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "10485760")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.services.storage import validate_upload

    class FakeFile:
        filename = "policy.pdf"
        content_type = "application/pdf"

    assert validate_upload(FakeFile(), 2048) == ".pdf"  # type: ignore[arg-type]


def test_validate_upload_rejects_oversized(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "100")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.services.storage import validate_upload

    class FakeFile:
        filename = "big.txt"
        content_type = "text/plain"

    with pytest.raises(HTTPException) as exc:
        validate_upload(FakeFile(), 101)  # type: ignore[arg-type]
    assert exc.value.status_code == 413


def test_extract_txt(tmp_path):
    from app.services.parsers import extract_text

    path = tmp_path / "note.txt"
    path.write_text("Hello knowledge base", encoding="utf-8")
    assert extract_text(str(path)) == "Hello knowledge base"


def test_jwt_roundtrip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from uuid import uuid4

    from app.core.security import create_access_token, decode_token, hash_password, verify_password

    uid = uuid4()
    token = create_access_token(uid)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == str(uid)
    assert payload["type"] == "access"
    hashed = hash_password("password123")
    assert verify_password("password123", hashed)
    assert not verify_password("wrong", hashed)
