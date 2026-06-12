"""HTML/CSS → PDF generation via Jinja2 + WeasyPrint.

Design goals:
- Renders are PURE FUNCTIONS of the stored Report snapshot. Two calls with the
  same inputs produce byte-identical PDFs (we strip the PDF metadata date that
  WeasyPrint stamps in by default).
- All layouts are absolutely positioned with fixed bubble sizes — number length
  cannot push elements around.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ---------- Jinja filters --------------------------------------------------
def _money(n) -> str:
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    sign = "-" if n < 0 else ""
    return f"{sign}${abs(int(round(n))):,}"


def _money_per_mo(n) -> str:
    return f"{_money(n)}/mo"


def _safe_name(s: Optional[str]) -> str:
    if not s:
        return ""
    norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    norm = re.sub(r"\s*&\s*", "_and_", norm)
    norm = re.sub(r"[^A-Za-z0-9._-]+", "_", norm).strip("_")
    return norm or "client"


_env.filters["money"] = _money
_env.filters["money_per_mo"] = _money_per_mo


# ---------- Domain helpers (snapshot → template context) -------------------
def _age(dob: Optional[date], on: Optional[date] = None) -> Optional[int]:
    if not dob:
        return None
    today = on or date.today()
    a = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        a -= 1
    return a


def household_name(client_dict: dict) -> str:
    c1 = client_dict["client1"]
    c2 = client_dict.get("client2")
    if not c2 or not client_dict.get("married"):
        return f"{c1['firstName']} {c1['lastName']}"
    same_last = c1["lastName"] == c2["lastName"]
    if same_last:
        return f"{c1['firstName']} & {c2['firstName']} {c1['lastName']}"
    return f"{c1['firstName']} {c1['lastName']} & {c2['firstName']} {c2['lastName']}"


def pdf_filename(client_dict: dict, kind: str, quarter: str) -> str:
    return f"{_safe_name(household_name(client_dict))}_{kind.upper()}_{_safe_name(quarter)}.pdf"


def _ret_accounts(client_dict: dict, spouse_key: str) -> list[dict]:
    return list(client_dict.get("retirement", {}).get(spouse_key, []) or [])


def _non_ret(client_dict: dict) -> list[dict]:
    return list(client_dict.get("nonRetirement") or [])


def _build_context(client_dict: dict, report_dict: dict) -> dict:
    calc = report_dict.get("calc") or {}
    balances = report_dict.get("balances") or {}
    liab_balances = report_dict.get("liabilities") or {}
    fin = report_dict.get("financials") or {}

    c1 = client_dict["client1"]
    c2 = client_dict.get("client2")

    def _person_card(p: Optional[dict], spouse_no: int) -> Optional[dict]:
        if not p:
            return None
        return {
            "spouse": spouse_no,
            "name": f"{p['firstName']} {p['lastName']}",
            "age": p.get("age") if p.get("age") is not None else _age(date.fromisoformat(p["dob"])) if p.get("dob") else None,
            "dob": p.get("dob") or "",
            "ssn": p.get("ssn") or "",
        }

    def _account_card(a: dict, balance_key: str) -> dict:
        bal = balances.get(a["id"], 0) or 0
        return {
            "id": a["id"],
            "type": a["type"],
            "last4": a["last4"],
            "name": a.get("name"),
            "balance": bal,
            # cash balance shown for "investment" (non-retirement) bubbles —
            # the data model dropped a dedicated cash field but the template
            # leaves the slot in case a future field_key cash:<id> is added.
            "cash": balances.get(f"cash:{a['id']}"),
        }

    ret1 = [_account_card(a, "bal") for a in _ret_accounts(client_dict, "1")]
    ret2 = [_account_card(a, "bal") for a in _ret_accounts(client_dict, "2")]
    nonret = [_account_card(a, "bal") for a in _non_ret(client_dict)]

    liabilities = []
    for l in client_dict.get("liabilities") or []:
        liabilities.append({
            "type": l["type"],
            "rate": l.get("rate"),
            "balance": liab_balances.get(l["id"], 0) or 0,
        })

    trust = client_dict.get("trust") or {"exists": False}
    return {
        "household": household_name(client_dict),
        "quarter": report_dict["quarter"],
        "report_date": report_dict["date"],
        "married": client_dict.get("married", False),
        "client1": _person_card(c1, 1),
        "client2": _person_card(c2, 2),
        "financials": {
            "inflow": fin.get("inflow", 0),
            "outflow": fin.get("outflow", 0),
            "deductibles": fin.get("deductibles", 0),
            "excess": calc.get("excess", 0),
        },
        "reserve": {
            "balance": calc.get("privateReserveBalance", report_dict.get("privateReserve", 0)),
            "target": calc.get("privateReserveTarget", 0),
        },
        "retirement": {"1": ret1, "2": ret2},
        "non_retirement": nonret,
        "trust": {
            "exists": bool(trust.get("exists")),
            "address": trust.get("address") or "",
            "zillow": report_dict.get("zillow", 0) or 0,
        },
        "liabilities": liabilities,
        "totals": {
            "c1_retirement": calc.get("c1Retirement", 0),
            "c2_retirement": calc.get("c2Retirement", 0),
            "non_retirement": calc.get("nonRetirement", 0),
            "trust_value": calc.get("trustValue", 0),
            "grand_net_worth": calc.get("grandNetWorth", 0),
            "liabilities_total": calc.get("liabilitiesTotal", 0),
        },
    }


# ---------- Render --------------------------------------------------------
def render_html(kind: str, client_dict: dict, report_dict: dict) -> str:
    if kind not in ("sacs", "tcc"):
        raise ValueError(f"unknown PDF kind: {kind}")
    tpl = _env.get_template(f"{kind}.html")
    return tpl.render(**_build_context(client_dict, report_dict), kind=kind)


def render_pdf(kind: str, client_dict: dict, report_dict: dict) -> bytes:
    # Import inside the function so test environments without WeasyPrint
    # system libs can still import this module (filename + preview still work).
    from weasyprint import HTML  # type: ignore

    html = render_html(kind, client_dict, report_dict)
    pdf_bytes = HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
    # Strip the embedded creation date so the same input produces the same
    # bytes — required for the "history reproduces identical PDFs" promise.
    return _strip_pdf_dates(pdf_bytes)


_PDF_DATE_RE = re.compile(rb"/(CreationDate|ModDate)\s*\(D:\d{14}([+-]\d{2}'\d{2}'|Z)?\)")


def _strip_pdf_dates(pdf: bytes) -> bytes:
    # Replace the volatile dates with a fixed epoch so output is deterministic.
    return _PDF_DATE_RE.sub(rb"/\1 (D:19700101000000Z)", pdf)
