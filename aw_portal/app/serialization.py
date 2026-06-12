"""ORM → API-shape conversion helpers."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from .calculations import AccountRef
from .models import Account, Client, Liability, Report


def compute_age(dob: Optional[date], on: Optional[date] = None) -> Optional[int]:
    if dob is None:
        return None
    today = on or date.today()
    a = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        a -= 1
    return a


def person_out(first, last, dob, ssn) -> dict:
    return {
        "firstName": first,
        "lastName": last,
        "dob": dob.isoformat() if dob else None,
        "ssn": ssn,
        "age": compute_age(dob),
    }


def client_to_dict(c: Client, last_report_date: Optional[date] = None) -> dict:
    ret1 = [a for a in c.accounts if a.category == "retirement" and a.owner == "client1"]
    ret2 = [a for a in c.accounts if a.category == "retirement" and a.owner == "client2"]
    nonret = [a for a in c.accounts if a.category == "non_retirement"]

    def acct(a: Account, with_spouse: Optional[int] = None) -> dict:
        d = {
            "id": a.id,
            "type": a.account_type,
            "last4": a.account_last4,
            "name": a.institution_name,
        }
        if with_spouse is not None:
            d["spouse"] = with_spouse
        return d

    return {
        "id": c.id,
        "married": c.married,
        "client1": person_out(c.first_name, c.last_name, c.dob, c.ssn_last4),
        "client2": (
            person_out(c.c2_first_name, c.c2_last_name, c.c2_dob, c.c2_ssn_last4)
            if c.married and c.c2_first_name
            else None
        ),
        "retirement": {
            "1": [acct(a, 1) for a in ret1],
            "2": [acct(a, 2) for a in ret2],
        },
        "nonRetirement": [acct(a) for a in nonret],
        "trust": {
            "exists": c.trust_exists,
            "address": c.trust_property_address,
        },
        "liabilities": [
            {"id": l.id, "type": l.liability_type, "rate": float(l.interest_rate) if l.interest_rate is not None else None}
            for l in c.liabilities
        ],
        "financials": {
            "inflow": float(c.monthly_salary),
            "outflow": float(c.monthly_expense_budget),
            "deductibles": float(c.insurance_deductibles_total),
        },
        "lastReportDate": last_report_date.isoformat() if last_report_date else None,
    }


def account_refs(c: Client) -> list[AccountRef]:
    out: list[AccountRef] = []
    for a in c.accounts:
        if a.category == "retirement":
            spouse = 1 if a.owner == "client1" else 2
        else:
            spouse = 0
        out.append(AccountRef(id=a.id, spouse=spouse))
    return out


def report_to_dict(r: Report, calc_dict: Optional[dict] = None) -> dict:
    snap = r.financials_snapshot or {}
    balances = {}
    liabilities = {}
    for e in r.entries:
        if e.field_key.startswith("bal:"):
            balances[e.field_key[4:]] = float(e.value)
        elif e.field_key.startswith("liab:"):
            liabilities[e.field_key[5:]] = float(e.value)

    zillow = snap.get("zillow", 0) or 0
    reserve = snap.get("private_reserve", 0) or 0
    fin = snap.get("financials") or {}

    return {
        "id": r.id,
        "quarter": r.quarter_label,
        "date": r.report_date.isoformat(),
        "balances": balances,
        "liabilities": liabilities,
        "zillow": float(zillow),
        "privateReserve": float(reserve),
        "financials": {
            "inflow": float(fin.get("inflow", 0) or 0),
            "outflow": float(fin.get("outflow", 0) or 0),
            "deductibles": float(fin.get("deductibles", 0) or 0),
        },
        "calc": calc_dict if calc_dict is not None else _calc_camel(r.calc_snapshot or {}),
        "createdAt": (r.created_at.isoformat(timespec="seconds") + "Z")
        if r.created_at and not r.created_at.tzinfo
        else (r.created_at.isoformat() if r.created_at else None),
    }


_CALC_KEY_MAP = {
    "excess": "excess",
    "private_reserve_target": "privateReserveTarget",
    "private_reserve_balance": "privateReserveBalance",
    "c1_retirement": "c1Retirement",
    "c2_retirement": "c2Retirement",
    "non_retirement": "nonRetirement",
    "trust_value": "trustValue",
    "grand_net_worth": "grandNetWorth",
    "liabilities_total": "liabilitiesTotal",
    "inflow": "inflow",
    "outflow": "outflow",
    "deductibles": "deductibles",
}


def _calc_camel(snake: dict) -> dict:
    out = {}
    for k, v in snake.items():
        ck = _CALC_KEY_MAP.get(k, k)
        try:
            out[ck] = float(v)
        except (TypeError, ValueError):
            out[ck] = v
    return out


def calc_to_camel(c) -> dict:
    return _calc_camel(c.as_dict())
