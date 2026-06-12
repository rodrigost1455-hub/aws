"""Optional Canva Connect API integration.

Activates only when CANVA_API_KEY is set. Failures here MUST NOT affect the
core PDF download flow — call sites are expected to handle CanvaError.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx

CANVA_API_KEY_ENV = "CANVA_API_KEY"
CANVA_API_BASE_ENV = "CANVA_API_BASE"
DEFAULT_BASE = "https://api.canva.com/rest/v1"
ASSET_UPLOAD_PATH = "/asset-uploads"
DESIGNS_PATH = "/designs"


class CanvaError(RuntimeError):
    def __init__(self, message: str, *, status: int = 500):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class CanvaUpload:
    asset_id: str
    asset_url: Optional[str]
    design_id: Optional[str]
    design_url: Optional[str]


def is_configured() -> bool:
    return bool(os.environ.get(CANVA_API_KEY_ENV))


def _client() -> httpx.Client:
    token = os.environ.get(CANVA_API_KEY_ENV)
    if not token:
        raise CanvaError("Canva export not configured", status=501)
    base = os.environ.get(CANVA_API_BASE_ENV, DEFAULT_BASE).rstrip("/")
    return httpx.Client(
        base_url=base,
        timeout=httpx.Timeout(20.0),
        headers={"Authorization": f"Bearer {token}"},
    )


def upload_pdf(name: str, pdf_bytes: bytes) -> CanvaUpload:
    """Upload a PDF as an asset and (best-effort) create a design from it.

    Wrapped in try/except by callers — never let this raise into the PDF flow.
    """
    if not is_configured():
        raise CanvaError("Canva export not configured", status=501)

    with _client() as c:
        # 1) Upload the PDF as an asset.
        files = {"file": (name, pdf_bytes, "application/pdf")}
        r = c.post(ASSET_UPLOAD_PATH, files=files, data={"name": name})
        if r.status_code >= 400:
            raise CanvaError(f"Canva asset upload failed ({r.status_code}): {r.text[:300]}", status=502)
        asset = r.json() or {}
        asset_id = asset.get("asset", {}).get("id") or asset.get("id")
        asset_url = asset.get("asset", {}).get("url") or asset.get("url")
        if not asset_id:
            raise CanvaError("Canva did not return an asset id", status=502)

        # 2) Create a design that embeds the asset.
        design_id: Optional[str] = None
        design_url: Optional[str] = None
        try:
            dr = c.post(DESIGNS_PATH, json={"design_type": "presentation", "asset_id": asset_id, "title": name})
            if dr.status_code < 400:
                d = dr.json() or {}
                design = d.get("design") or d
                design_id = design.get("id")
                design_url = design.get("urls", {}).get("edit_url") or design.get("url")
        except httpx.HTTPError:
            # Design creation is best-effort — we still return the uploaded asset.
            pass

        return CanvaUpload(
            asset_id=asset_id,
            asset_url=asset_url,
            design_id=design_id,
            design_url=design_url,
        )
