"""Regression tests for the fixed vulnerabilities in SECURITY-AUDIT.md.

Run just these with:  pytest -m security
"""
import io
import json

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.config import Settings

pytestmark = pytest.mark.security


# --- JV-02: hardcoded / weak SECRET_KEY (CWE-798) ----------------------------

def test_settings_rejects_placeholder_secret(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "change-me-in-production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_short_secret(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "tooshort")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_accepts_strong_secret(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "z" * 48)
    assert Settings(_env_file=None).SECRET_KEY == "z" * 48


# --- JV-03: malformed token subject returns 401, not 500 (CWE-703) -----------

@pytest.mark.asyncio
async def test_malformed_subject_returns_401_not_500(client: AsyncClient):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.config import get_settings

    settings = get_settings()
    token = jwt.encode(
        {"sub": "not-a-uuid",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )
    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# --- JV-04: /jobs/import hardening (CWE-400) ----------------------------------

@pytest.mark.asyncio
async def test_import_rejects_oversized_file(auth_client: AsyncClient):
    big = b'[{"title":"x"}]' + b" " * (2 * 1024 * 1024 + 1)
    resp = await auth_client.post(
        "/jobs/import",
        files={"file": ("big.json", io.BytesIO(big), "application/json")},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_import_rejects_malformed_json(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/jobs/import",
        files={"file": ("bad.json", io.BytesIO(b"{not valid json"), "application/json")},
    )
    assert resp.status_code == 400   # not a 500


@pytest.mark.asyncio
async def test_import_rejects_unsupported_type(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/jobs/import",
        files={"file": ("x.html", io.BytesIO(b"<html>"), "text/html")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_import_accepts_valid_json(auth_client: AsyncClient):
    payload = json.dumps([{"title": "Engineer", "company": "Acme", "url": "https://x/1"}])
    resp = await auth_client.post(
        "/jobs/import",
        files={"file": ("ok.json", io.BytesIO(payload.encode()), "application/json")},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
