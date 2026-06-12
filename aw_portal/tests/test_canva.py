"""Canva integration — env-var gating + httpx-mocked upload happy path."""
from __future__ import annotations

import os
from unittest.mock import patch

import httpx
import pytest

from app import canva


def test_not_configured_without_env_var(monkeypatch):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)
    assert canva.is_configured() is False
    with pytest.raises(canva.CanvaError) as ei:
        canva.upload_pdf("x.pdf", b"%PDF-1.4")
    assert ei.value.status == 501


def test_configured_uploads_and_creates_design(monkeypatch):
    monkeypatch.setenv("CANVA_API_KEY", "test-token")

    def handler(request: httpx.Request) -> httpx.Response:
        # Verify auth header & route dispatch
        assert request.headers["Authorization"] == "Bearer test-token"
        if request.url.path.endswith("/asset-uploads"):
            return httpx.Response(200, json={"asset": {"id": "asset_abc", "url": "https://canva/asset_abc"}})
        if request.url.path.endswith("/designs"):
            return httpx.Response(200, json={"design": {"id": "design_xyz", "urls": {"edit_url": "https://canva/design/xyz"}}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    with patch.object(httpx, "Client", fake_client):
        result = canva.upload_pdf("Robert_Harrington_SACS_Q1_2026.pdf", b"%PDF-1.4 fake")

    assert result.asset_id == "asset_abc"
    assert result.asset_url == "https://canva/asset_abc"
    assert result.design_id == "design_xyz"
    assert result.design_url == "https://canva/design/xyz"


def test_design_failure_still_returns_asset(monkeypatch):
    monkeypatch.setenv("CANVA_API_KEY", "test-token")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/asset-uploads"):
            return httpx.Response(200, json={"asset": {"id": "asset_abc"}})
        if request.url.path.endswith("/designs"):
            return httpx.Response(500, text="boom")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    with patch.object(httpx, "Client", fake_client):
        result = canva.upload_pdf("x.pdf", b"%PDF")

    assert result.asset_id == "asset_abc"
    assert result.design_id is None  # best-effort, not raised


def test_asset_upload_failure_raises_canva_error(monkeypatch):
    monkeypatch.setenv("CANVA_API_KEY", "test-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad token")

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    with patch.object(httpx, "Client", fake_client):
        with pytest.raises(canva.CanvaError) as ei:
            canva.upload_pdf("x.pdf", b"%PDF")
    assert ei.value.status == 502
