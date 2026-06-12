"""DB helpers — client upsert/reconcile, last-values, calculation glue."""
from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import ids, models, schemas
from .calculations import AccountRef, CalcInputs, calculate as run_calc


# --------------------------- queries ---------------------------------------
def list_clients(db: Session) -> list[models.Client]:
    return list(
        db.scalars(
            select(models.Client)
            .options(
                selectinload(models.Client.accounts),
                selectinload(models.Client.liabilities),
            )
            .order_by(models.Client.created_at.asc())
        )
    )


def get_client(db: Session, cid: str) -> Optional[models.Client]:
    return db.scalar(
        select(models.Client)
        .where(models.Client.id == cid)
        .options(
            selectinload(models.Client.accounts),
            selectinload(models.Client.liabilities),
        )
    )


def last_report_date(db: Session, cid: str) -> Optional[_date]:
    return db.scalar(
        select(models.Report.report_date)
        .where(models.Report.client_id == cid)
        .order_by(models.Report.report_date.desc())
        .limit(1)
    )


def latest_report(db: Session, cid: str) -> Optional[models.Report]:
    return db.scalar(
        select(models.Report)
        .where(models.Report.client_id == cid)
        .order_by(models.Report.created_at.desc())
        .options(selectinload(models.Report.entries))
        .limit(1)
    )


def list_reports(db: Session, cid: str) -> list[models.Report]:
    return list(
        db.scalars(
            select(models.Report)
            .where(models.Report.client_id == cid)
            .options(selectinload(models.Report.entries))
            .order_by(models.Report.created_at.desc())
        )
    )


def get_report(db: Session, rid: str) -> Optional[models.Report]:
    return db.scalar(
        select(models.Report)
        .where(models.Report.id == rid)
        .options(selectinload(models.Report.entries))
    )


# --------------------------- writes ----------------------------------------
def _decimal(x) -> Decimal:
    if x is None or x == "":
        return Decimal("0")
    return x if isinstance(x, Decimal) else Decimal(str(x))


def create_client(db: Session, payload: schemas.ClientIn) -> models.Client:
    c = models.Client(
        id=payload.id or ids.client_id(),
        married=payload.married,
        first_name=payload.client1.first_name,
        last_name=payload.client1.last_name,
        dob=payload.client1.dob,
        ssn_last4=payload.client1.ssn,
        trust_exists=payload.trust.exists,
        trust_property_address=payload.trust.address if payload.trust.exists else None,
        monthly_salary=_decimal(payload.financials.inflow),
        monthly_expense_budget=_decimal(payload.financials.outflow),
        insurance_deductibles_total=_decimal(payload.financials.deductibles),
    )
    if payload.married and payload.client2:
        c.c2_first_name = payload.client2.first_name
        c.c2_last_name = payload.client2.last_name
        c.c2_dob = payload.client2.dob
        c.c2_ssn_last4 = payload.client2.ssn

    _apply_accounts(c, payload, fresh=True)
    _apply_liabilities(c, payload, fresh=True)

    db.add(c)
    db.flush()
    return c


def update_client(db: Session, c: models.Client, payload: schemas.ClientIn) -> models.Client:
    c.married = payload.married
    c.first_name = payload.client1.first_name
    c.last_name = payload.client1.last_name
    c.dob = payload.client1.dob
    c.ssn_last4 = payload.client1.ssn

    if payload.married and payload.client2:
        c.c2_first_name = payload.client2.first_name
        c.c2_last_name = payload.client2.last_name
        c.c2_dob = payload.client2.dob
        c.c2_ssn_last4 = payload.client2.ssn
    else:
        c.c2_first_name = None
        c.c2_last_name = None
        c.c2_dob = None
        c.c2_ssn_last4 = None

    c.trust_exists = payload.trust.exists
    c.trust_property_address = payload.trust.address if payload.trust.exists else None
    c.monthly_salary = _decimal(payload.financials.inflow)
    c.monthly_expense_budget = _decimal(payload.financials.outflow)
    c.insurance_deductibles_total = _decimal(payload.financials.deductibles)

    _apply_accounts(c, payload, fresh=False)
    _apply_liabilities(c, payload, fresh=False)
    db.flush()
    return c


# --- account / liability reconciliation -----------------------------------
def _apply_accounts(c: models.Client, payload: schemas.ClientIn, fresh: bool) -> None:
    incoming: list[tuple[str, str, "schemas.RetirementAccountIn | schemas.NonRetirementAccountIn", int]] = []
    for key, owner in (("1", "client1"), ("2", "client2")):
        for i, a in enumerate(payload.retirement.get(key, []) or []):
            incoming.append(("retirement", owner, a, i))
    for i, a in enumerate(payload.non_retirement or []):
        incoming.append(("non_retirement", "joint", a, i))

    by_id = {a.id: a for a in c.accounts}
    seen_ids: set[str] = set()
    next_sort = 0

    for category, owner, a, idx in incoming:
        existing = by_id.get(a.id) if a.id else None
        if existing is None:
            existing = models.Account(id=a.id or ids.account_id(), client_id=c.id)
            c.accounts.append(existing)
        existing.client_id = c.id
        existing.owner = owner
        existing.category = category
        existing.account_type = a.type
        existing.account_last4 = a.last4
        existing.institution_name = a.name
        existing.sort_order = next_sort
        next_sort += 1
        seen_ids.add(existing.id)

    # delete dropped
    if not fresh:
        c.accounts[:] = [a for a in c.accounts if a.id in seen_ids]


def _apply_liabilities(c: models.Client, payload: schemas.ClientIn, fresh: bool) -> None:
    by_id = {l.id: l for l in c.liabilities}
    seen_ids: set[str] = set()
    for i, l in enumerate(payload.liabilities or []):
        existing = by_id.get(l.id) if l.id else None
        if existing is None:
            existing = models.Liability(id=l.id or ids.liability_id(), client_id=c.id)
            c.liabilities.append(existing)
        existing.client_id = c.id
        existing.liability_type = l.type
        existing.interest_rate = (
            _decimal(l.rate) if l.rate is not None else None
        )
        existing.sort_order = i
        seen_ids.add(existing.id)

    if not fresh:
        c.liabilities[:] = [l for l in c.liabilities if l.id in seen_ids]


# --------------------------- last-values -----------------------------------
def last_values(db: Session, cid: str) -> Optional[dict]:
    r = latest_report(db, cid)
    if r is None:
        return None
    balances: dict[str, Decimal] = {}
    liabilities: dict[str, Decimal] = {}
    zillow = Decimal("0")
    reserve = Decimal("0")
    for e in r.entries:
        if e.field_key.startswith("bal:"):
            balances[e.field_key[4:]] = e.value
        elif e.field_key.startswith("liab:"):
            liabilities[e.field_key[5:]] = e.value
        elif e.field_key == "zillow":
            zillow = e.value
        elif e.field_key == "reserve":
            reserve = e.value
    return {
        "quarter": r.quarter_label,
        "balances": balances,
        "liabilities": liabilities,
        "zillow": zillow,
        "private_reserve": reserve,
    }


# --------------------------- calculation glue ------------------------------
def calculate_for(c: models.Client, payload: schemas.CalculateIn):
    refs: list[AccountRef] = []
    for a in c.accounts:
        spouse = 1 if a.owner == "client1" else 2 if a.owner == "client2" else 0
        refs.append(AccountRef(id=a.id, spouse=spouse))
    return run_calc(
        CalcInputs(
            accounts=refs,
            trust_exists=c.trust_exists,
            financials={
                "inflow": payload.financials.inflow,
                "outflow": payload.financials.outflow,
                "deductibles": payload.financials.deductibles,
            },
            balances=payload.balances,
            liabilities=payload.liabilities,
            zillow=payload.zillow or 0,
            private_reserve=payload.private_reserve or 0,
        )
    )
