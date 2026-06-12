from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


MONEY = Numeric(18, 2)


def _utcnow() -> datetime:
    return datetime.utcnow()


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    married: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    ssn_last4: Mapped[str] = mapped_column(String(4), nullable=False)

    c2_first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    c2_last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    c2_dob: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    c2_ssn_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)

    trust_exists: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trust_property_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    monthly_salary: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    monthly_expense_budget: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    insurance_deductibles_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="Account.sort_order",
    )
    liabilities: Mapped[list["Liability"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="Report.created_at.desc()",
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    owner: Mapped[str] = mapped_column(String, nullable=False)        # client1|client2|joint
    category: Mapped[str] = mapped_column(String, nullable=False)     # retirement|non_retirement
    account_type: Mapped[str] = mapped_column(String, nullable=False) # IRA / Roth IRA / 401K / Pension / Brokerage / Joint
    account_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    institution_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    client: Mapped[Client] = relationship(back_populates="accounts")


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    liability_type: Mapped[str] = mapped_column(String, nullable=False)
    interest_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    client: Mapped[Client] = relationship(back_populates="liabilities")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    quarter_label: Mapped[str] = mapped_column(String, nullable=False)
    financials_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    calc_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    client: Mapped[Client] = relationship(back_populates="reports")
    entries: Mapped[list["ReportEntry"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )


class ReportEntry(Base):
    __tablename__ = "report_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    report_id: Mapped[str] = mapped_column(String, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    report: Mapped[Report] = relationship(back_populates="entries")
