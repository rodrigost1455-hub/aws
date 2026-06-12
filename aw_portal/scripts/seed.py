"""Load the same 6 demo households as the prototype's data.js seed.

Usage:
    python -m scripts.seed         # idempotent: only seeds if DB is empty
    python -m scripts.seed --force # wipe and reseed
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app import ids
from app.database import SessionLocal, init_db
from app.models import Account, Client, Liability, Report, ReportEntry


def _person(first, last, dob, ssn):
    return {"first": first, "last": last, "dob": date.fromisoformat(dob), "ssn": ssn}


HOUSEHOLDS = [
    {
        "id": "c-harrington",
        "married": True,
        "c1": _person("Robert", "Harrington", "1958-03-14", "4417"),
        "c2": _person("Eleanor", "Harrington", "1960-09-02", "2290"),
        "ret1": [("IRA", "8841", 1280000), ("401K", "1120", 940000), ("Pension", "5567", 410000)],
        "ret2": [("Roth IRA", "3392", 620000), ("IRA", "7714", 305000)],
        "nonret": [("Brokerage", "9001", "Schwab", 1840000), ("Joint", "4420", "Joint", 260000)],
        "trust": {"exists": True, "address": "118 Beacon Hill Rd, Greenwich, CT 06830", "zillow": 3450000},
        "liab": [("Mortgage", 3.25, 412000), ("Auto Loan", 5.9, 38000)],
        "fin": (41500, 24000, 28000),
        "last_report": "2026-03-31",
        "reserve": 152000,
    },
    {
        "id": "c-nakamura",
        "married": True,
        "c1": _person("Kenji", "Nakamura", "1965-11-21", "1182"),
        "c2": _person("Lydia", "Nakamura", "1967-06-30", "7741"),
        "ret1": [("401K", "2231", 1120000), ("Roth IRA", "8890", 380000)],
        "ret2": [("IRA", "5512", 540000)],
        "nonret": [("Brokerage", "3301", "Fidelity", 970000)],
        "trust": {"exists": False, "address": "", "zillow": 0},
        "liab": [("Mortgage", 2.85, 295000)],
        "fin": (33800, 19500, 19000),
        "last_report": "2026-03-31",
        "reserve": 96000,
    },
    {
        "id": "c-okonkwo",
        "married": False,
        "c1": _person("Adaeze", "Okonkwo", "1972-01-08", "6634"),
        "c2": None,
        "ret1": [("IRA", "1199", 720000), ("401K", "4456", 615000)],
        "ret2": [],
        "nonret": [("Brokerage", "7788", "Schwab", 1330000), ("Brokerage", "2014", "Vanguard", 410000)],
        "trust": {"exists": True, "address": "44 Lakeshore Dr, Austin, TX 78703", "zillow": 1980000},
        "liab": [],
        "fin": (28200, 14800, 12000),
        "last_report": "2026-03-31",
        "reserve": 88000,
    },
    {
        "id": "c-delacroix",
        "married": True,
        "c1": _person("Henri", "Delacroix", "1955-07-19", "9921"),
        "c2": _person("Margaux", "Delacroix", "1957-12-11", "3308"),
        "ret1": [("Pension", "6620", 880000), ("IRA", "1145", 1010000)],
        "ret2": [("Roth IRA", "7732", 455000), ("401K", "9980", 690000)],
        "nonret": [("Joint", "5540", "Joint Brokerage", 2210000)],
        "trust": {"exists": True, "address": "9 Carmel Valley Rd, Carmel, CA 93923", "zillow": 4120000},
        "liab": [("Mortgage", 4.1, 510000), ("Auto Loan", 6.4, 31000), ("Auto Loan", 5.5, 27000)],
        "fin": (52000, 31000, 35000),
        "last_report": "2025-12-31",
        "reserve": 221000,
    },
    {
        "id": "c-ferraro",
        "married": False,
        "c1": _person("Sofia", "Ferraro", "1980-04-25", "2256"),
        "c2": None,
        "ret1": [("Roth IRA", "3380", 340000)],
        "ret2": [],
        "nonret": [("Brokerage", "1102", "Schwab", 760000)],
        "trust": {"exists": False, "address": "", "zillow": 0},
        "liab": [("Auto Loan", 4.9, 22000)],
        "fin": (22500, 12200, 9000),
        "last_report": None,
        "reserve": 0,
    },
    {
        "id": "c-whitfield",
        "married": True,
        "c1": _person("James", "Whitfield", "1962-10-05", "8812"),
        "c2": _person("Catherine", "Whitfield", "1963-02-17", "4471"),
        "ret1": [("401K", "5523", 1450000), ("IRA", "9087", 720000)],
        "ret2": [("IRA", "3361", 410000), ("Roth IRA", "6648", 290000)],
        "nonret": [("Brokerage", "7240", "Morgan Stanley", 2050000), ("Joint", "8830", "Joint", 340000)],
        "trust": {"exists": True, "address": "27 Highland Ave, Wellesley, MA 02481", "zillow": 2760000},
        "liab": [("Mortgage", 3.5, 364000)],
        "fin": (46800, 27500, 31000),
        "last_report": "2026-03-31",
        "reserve": 178000,
    },
]


def _quarter_label(d: date) -> str:
    return f"Q{(d.month - 1)//3 + 1} {d.year}"


def _D(x):
    return Decimal(str(x))


def _seed_one(db, h):
    c = Client(
        id=h["id"],
        married=h["married"],
        first_name=h["c1"]["first"],
        last_name=h["c1"]["last"],
        dob=h["c1"]["dob"],
        ssn_last4=h["c1"]["ssn"],
        trust_exists=h["trust"]["exists"],
        trust_property_address=h["trust"]["address"] or None,
        monthly_salary=_D(h["fin"][0]),
        monthly_expense_budget=_D(h["fin"][1]),
        insurance_deductibles_total=_D(h["fin"][2]),
    )
    if h["c2"]:
        c.c2_first_name = h["c2"]["first"]
        c.c2_last_name = h["c2"]["last"]
        c.c2_dob = h["c2"]["dob"]
        c.c2_ssn_last4 = h["c2"]["ssn"]

    sort = 0
    bal_map: dict[str, Decimal] = {}
    for typ, last4, bal in h["ret1"]:
        a = Account(id=ids.account_id(), client_id=c.id, owner="client1", category="retirement",
                    account_type=typ, account_last4=last4, sort_order=sort)
        c.accounts.append(a); bal_map[a.id] = _D(bal); sort += 1
    for typ, last4, bal in h["ret2"]:
        a = Account(id=ids.account_id(), client_id=c.id, owner="client2", category="retirement",
                    account_type=typ, account_last4=last4, sort_order=sort)
        c.accounts.append(a); bal_map[a.id] = _D(bal); sort += 1
    for typ, last4, name, bal in h["nonret"]:
        a = Account(id=ids.account_id(), client_id=c.id, owner="joint", category="non_retirement",
                    account_type=typ, account_last4=last4, institution_name=name, sort_order=sort)
        c.accounts.append(a); bal_map[a.id] = _D(bal); sort += 1

    liab_map: dict[str, Decimal] = {}
    for i, (typ, rate, bal) in enumerate(h["liab"]):
        l = Liability(id=ids.liability_id(), client_id=c.id, liability_type=typ,
                      interest_rate=_D(rate), sort_order=i)
        c.liabilities.append(l); liab_map[l.id] = _D(bal)

    db.add(c)
    db.flush()

    if h["last_report"]:
        rd = date.fromisoformat(h["last_report"])
        zillow = _D(h["trust"]["zillow"]) if h["trust"]["exists"] else _D(0)
        reserve = _D(h["reserve"])
        from app.calculations import AccountRef, CalcInputs, calculate
        refs = [
            AccountRef(a.id, 1 if a.owner == "client1" else 2 if a.owner == "client2" else 0)
            for a in c.accounts
        ]
        calc = calculate(CalcInputs(
            accounts=refs,
            trust_exists=c.trust_exists,
            financials={"inflow": c.monthly_salary, "outflow": c.monthly_expense_budget, "deductibles": c.insurance_deductibles_total},
            balances=bal_map,
            liabilities=liab_map,
            zillow=zillow,
            private_reserve=reserve,
        ))
        fin_snap = {
            "financials": {
                "inflow": float(c.monthly_salary),
                "outflow": float(c.monthly_expense_budget),
                "deductibles": float(c.insurance_deductibles_total),
            },
            "zillow": float(zillow),
            "private_reserve": float(reserve),
        }
        calc_snap = {k: float(v) if isinstance(v, Decimal) else v for k, v in calc.as_dict().items()}
        r = Report(
            id=ids.report_id(),
            client_id=c.id,
            report_date=rd,
            quarter_label=_quarter_label(rd),
            financials_snapshot=fin_snap,
            calc_snapshot=calc_snap,
            created_at=datetime.combine(rd, datetime.min.time()).replace(hour=16),
        )
        for aid, bal in bal_map.items():
            r.entries.append(ReportEntry(id=ids.entry_id(), field_key=f"bal:{aid}", value=bal))
        for lid, bal in liab_map.items():
            r.entries.append(ReportEntry(id=ids.entry_id(), field_key=f"liab:{lid}", value=bal))
        r.entries.append(ReportEntry(id=ids.entry_id(), field_key="reserve", value=reserve))
        if c.trust_exists:
            r.entries.append(ReportEntry(id=ids.entry_id(), field_key="zillow", value=zillow))
        for k in ("inflow", "outflow", "deductibles"):
            r.entries.append(ReportEntry(id=ids.entry_id(), field_key=k, value=_D(fin_snap["financials"][k])))
        db.add(r)


def seed_if_empty() -> int:
    init_db()
    with SessionLocal() as db:
        existing = db.scalar(select(Client).limit(1))
        if existing:
            return 0
        for h in HOUSEHOLDS:
            _seed_one(db, h)
        db.commit()
        return len(HOUSEHOLDS)


def seed_demo() -> int:
    """Always seed — useful when you want to top up. Skips households that exist."""
    init_db()
    with SessionLocal() as db:
        added = 0
        for h in HOUSEHOLDS:
            if db.get(Client, h["id"]):
                continue
            _seed_one(db, h)
            added += 1
        db.commit()
        return added


def _wipe():
    from app.database import engine
    from app.database import Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def main():
    force = "--force" in sys.argv
    if force:
        _wipe()
        print(f"seeded {seed_demo()} households (force)")
    else:
        n = seed_if_empty()
        print(f"seeded {n} households" if n else "DB already populated — nothing to do")


if __name__ == "__main__":
    main()
