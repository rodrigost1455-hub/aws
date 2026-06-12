"""End-to-end smoke tests against the FastAPI app with a fresh SQLite file."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Point the DB at a fresh temp file BEFORE importing the app.
_tmp = Path(tempfile.mkdtemp()) / "test_portal.db"
os.environ["RAILWAY_DATABASE_PATH"] = str(_tmp)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _bootstrap():
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _new_client_payload():
    return {
        "married": True,
        "client1": {"firstName": "Robert", "lastName": "Harrington", "dob": "1958-03-14", "ssn": "4417"},
        "client2": {"firstName": "Eleanor", "lastName": "Harrington", "dob": "1960-09-02", "ssn": "2290"},
        "retirement": {
            "1": [{"spouse": 1, "type": "IRA", "last4": "8841"}],
            "2": [{"spouse": 2, "type": "Roth IRA", "last4": "3392"}],
        },
        "nonRetirement": [{"type": "Brokerage", "last4": "9001", "name": "Schwab"}],
        "trust": {"exists": True, "address": "118 Beacon Hill Rd, Greenwich, CT 06830"},
        "liabilities": [{"type": "Mortgage", "rate": 3.25}],
        "financials": {"inflow": 41500, "outflow": 24000, "deductibles": 28000},
    }


def test_create_client_and_stable_ids(client):
    r = client.post("/api/clients", json=_new_client_payload())
    assert r.status_code == 201, r.text
    c = r.json()
    cid = c["id"]
    assert cid.startswith("c-")
    a_id = c["retirement"]["1"][0]["id"]
    l_id = c["liabilities"][0]["id"]

    # PUT roundtrip — keep the ids; add a new account
    payload = _new_client_payload()
    payload["id"] = cid
    payload["retirement"]["1"][0]["id"] = a_id
    payload["liabilities"][0]["id"] = l_id
    payload["nonRetirement"].append({"type": "Joint", "last4": "4420", "name": "Joint"})

    r = client.put(f"/api/clients/{cid}", json=payload)
    assert r.status_code == 200, r.text
    c2 = r.json()
    assert c2["retirement"]["1"][0]["id"] == a_id
    assert c2["liabilities"][0]["id"] == l_id
    assert len(c2["nonRetirement"]) == 2


def test_report_missing_keys_returns_422(client):
    r = client.post("/api/clients", json=_new_client_payload())
    cid = r.json()["id"]

    # Missing reserve + the account balance.
    r = client.post(
        f"/api/clients/{cid}/reports",
        json={
            "quarter": "Q1 2026",
            "date": "2026-03-31",
            "balances": {},
            "liabilities": {},
            "zillow": 3450000,
            "privateReserve": 0,
            "financials": {"inflow": 41500, "outflow": 24000, "deductibles": 28000},
        },
    )
    # privateReserve=0 still counts as a value, so reserve is satisfied.
    assert r.status_code == 422
    missing = r.json()["missing"]
    assert any(k.startswith("bal:") for k in missing)
    assert any(k.startswith("liab:") for k in missing)


def test_report_create_and_pdf(client):
    c = client.post("/api/clients", json=_new_client_payload()).json()
    cid = c["id"]
    bal_id = c["retirement"]["1"][0]["id"]
    bal_id2 = c["retirement"]["2"][0]["id"]
    nr_id = c["nonRetirement"][0]["id"]
    liab_id = c["liabilities"][0]["id"]

    payload = {
        "quarter": "Q1 2026",
        "date": "2026-03-31",
        "balances": {bal_id: 1280000, bal_id2: 620000, nr_id: 1840000},
        "liabilities": {liab_id: 412000},
        "zillow": 3450000,
        "privateReserve": 152000,
        "financials": {"inflow": 41500, "outflow": 24000, "deductibles": 28000},
    }
    r = client.post(f"/api/clients/{cid}/reports", json=payload)
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["calc"]["grandNetWorth"] == 1280000 + 620000 + 1840000 + 3450000
    assert rep["calc"]["liabilitiesTotal"] == 412000

    rid = rep["id"]
    # Preview endpoint (HTML) always works — covers the templates+context path
    # without depending on WeasyPrint's native libs.
    prev = client.get(f"/api/reports/{rid}/preview", params={"type": "sacs"})
    assert prev.status_code == 200
    # SACS page 1 has household + financials; page 2 shows reserve + non-ret accounts.
    assert "Harrington" in prev.text
    assert "$152,000" in prev.text   # reserve balance
    assert "$1,840,000" in prev.text # the non-retirement account balance

    from ._pdf_helpers import weasyprint_available
    if weasyprint_available():
        pdf = client.get(f"/api/reports/{rid}/pdf", params={"type": "sacs"})
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content[:4] == b"%PDF"
        # filename built from client name
        assert "Harrington_SACS_Q1_2026.pdf" in pdf.headers["content-disposition"]

    # last-values reflects the saved report
    lv = client.get(f"/api/clients/{cid}/last-values").json()
    assert lv["balances"][bal_id] == 1280000
    assert lv["liabilities"][liab_id] == 412000
    assert lv["zillow"] == 3450000
    assert lv["privateReserve"] == 152000


def test_canva_stub_returns_501(client):
    c = client.post("/api/clients", json=_new_client_payload()).json()
    cid = c["id"]
    bal_id = c["retirement"]["1"][0]["id"]
    bal_id2 = c["retirement"]["2"][0]["id"]
    nr_id = c["nonRetirement"][0]["id"]
    liab_id = c["liabilities"][0]["id"]

    rep = client.post(
        f"/api/clients/{cid}/reports",
        json={
            "quarter": "Q1 2026", "date": "2026-03-31",
            "balances": {bal_id: 1, bal_id2: 1, nr_id: 1},
            "liabilities": {liab_id: 1},
            "zillow": 1, "privateReserve": 1,
            "financials": {"inflow": 1, "outflow": 1, "deductibles": 1},
        },
    ).json()
    r = client.post(f"/api/reports/{rep['id']}/export-canva")
    assert r.status_code == 501
    assert "Canva export not configured" in r.json()["detail"]
