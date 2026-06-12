"""Test helpers — fixtures + the WeasyPrint availability probe.

WeasyPrint requires native libraries (pango/cairo) at import time. On dev
machines without them — Windows in particular — we want the HTML/preview
tests to still run, so we skip only the actual PDF render tests.
"""
from __future__ import annotations

import pytest


def weasyprint_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except Exception:
        return False
    try:
        from weasyprint import HTML
        HTML(string="<p>probe</p>").write_pdf()
        return True
    except Exception:
        return False


requires_weasyprint = pytest.mark.skipif(
    not weasyprint_available(),
    reason="WeasyPrint native libs not available (install GTK on Windows or use the Docker image)",
)


# ---- Synthetic client/report dicts (no DB) -------------------------------

def make_client(*, married=True, ret1=1, ret2=1, nonret=1, liabilities=1, trust=True, c2_last=None):
    last2 = c2_last or "Harrington"
    c = {
        "id": "c-test",
        "married": married,
        "client1": {"firstName": "Robert", "lastName": "Harrington", "dob": "1958-03-14", "ssn": "4417", "age": 68},
        "client2": ({"firstName": "Eleanor", "lastName": last2, "dob": "1960-09-02", "ssn": "2290", "age": 65} if married else None),
        "retirement": {
            "1": [{"id": f"r1-{i}", "spouse": 1, "type": ["IRA", "401K", "Roth IRA", "Pension", "IRA", "401K"][i % 6], "last4": f"00{i:02d}", "name": None} for i in range(ret1)],
            "2": [{"id": f"r2-{i}", "spouse": 2, "type": ["Roth IRA", "IRA", "401K", "Pension", "IRA", "Roth IRA"][i % 6], "last4": f"99{i:02d}", "name": None} for i in range(ret2)],
        },
        "nonRetirement": [{"id": f"nr-{i}", "type": "Brokerage", "last4": f"55{i:02d}", "name": ["Schwab", "Fidelity", "Vanguard", "Morgan Stanley", "Joint", "BNY"][i % 6]} for i in range(nonret)],
        "trust": {"exists": trust, "address": "118 Beacon Hill Rd, Greenwich, CT 06830" if trust else None},
        "liabilities": [{"id": f"l-{i}", "type": ["Mortgage", "Auto Loan", "Auto Loan"][i % 3], "rate": [3.25, 5.9, 4.1][i % 3]} for i in range(liabilities)],
        "financials": {"inflow": 41500, "outflow": 24000, "deductibles": 28000},
        "lastReportDate": "2026-03-31",
    }
    return c


def make_report(client_dict, *, balance_per_acct=1_000_000, liab_per=100_000, zillow=3_450_000, reserve=152_000, fin=None):
    balances = {}
    for a in client_dict["retirement"]["1"] + client_dict["retirement"]["2"] + client_dict["nonRetirement"]:
        balances[a["id"]] = balance_per_acct
    liab_balances = {l["id"]: liab_per for l in client_dict["liabilities"]}

    fin = fin or {"inflow": 41500, "outflow": 24000, "deductibles": 28000}
    # totals
    c1 = sum(balances[a["id"]] for a in client_dict["retirement"]["1"])
    c2 = sum(balances[a["id"]] for a in client_dict["retirement"]["2"])
    nr = sum(balances[a["id"]] for a in client_dict["nonRetirement"])
    trust_val = zillow if client_dict["trust"]["exists"] else 0
    grand = c1 + c2 + nr + trust_val
    liab_total = sum(liab_balances.values())

    return {
        "id": "rep-test",
        "quarter": "Q1 2026",
        "date": "2026-03-31",
        "balances": balances,
        "liabilities": liab_balances,
        "zillow": trust_val,
        "privateReserve": reserve,
        "financials": fin,
        "calc": {
            "excess": fin["inflow"] - fin["outflow"],
            "privateReserveTarget": 6 * fin["outflow"] + fin["deductibles"],
            "privateReserveBalance": reserve,
            "c1Retirement": c1,
            "c2Retirement": c2,
            "nonRetirement": nr,
            "trustValue": trust_val,
            "grandNetWorth": grand,
            "liabilitiesTotal": liab_total,
            "inflow": fin["inflow"],
            "outflow": fin["outflow"],
            "deductibles": fin["deductibles"],
        },
        "createdAt": "2026-03-31T16:00:00Z",
    }
