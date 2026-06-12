from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ---- Person ----------------------------------------------------------------
class PersonIn(_CamelModel):
    first_name: str
    last_name: str
    dob: date
    ssn: str = Field(min_length=4, max_length=4)

    @field_validator("ssn")
    @classmethod
    def _digits4(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 4:
            raise ValueError("ssn must be 4 digits")
        return v


class PersonOut(_CamelModel):
    first_name: str
    last_name: str
    dob: date
    ssn: str
    age: Optional[int] = None


# ---- Accounts --------------------------------------------------------------
class RetirementAccountIn(_CamelModel):
    id: Optional[str] = None
    spouse: int  # 1 | 2
    type: str
    last4: str = Field(min_length=4, max_length=4)
    name: Optional[str] = None

    @field_validator("last4")
    @classmethod
    def _digits4(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 4:
            raise ValueError("last4 must be 4 digits")
        return v


class NonRetirementAccountIn(_CamelModel):
    id: Optional[str] = None
    type: str
    last4: str = Field(min_length=4, max_length=4)
    name: Optional[str] = None

    @field_validator("last4")
    @classmethod
    def _digits4(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 4:
            raise ValueError("last4 must be 4 digits")
        return v


class RetirementAccountOut(_CamelModel):
    id: str
    spouse: int
    type: str
    last4: str
    name: Optional[str] = None


class NonRetirementAccountOut(_CamelModel):
    id: str
    type: str
    last4: str
    name: Optional[str] = None


class RetirementBuckets(_CamelModel):
    one: list[RetirementAccountOut] = Field(default_factory=list, alias="1")
    two: list[RetirementAccountOut] = Field(default_factory=list, alias="2")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# ---- Liabilities -----------------------------------------------------------
class LiabilityIn(_CamelModel):
    id: Optional[str] = None
    type: str
    rate: Optional[Decimal] = None


class LiabilityOut(_CamelModel):
    id: str
    type: str
    rate: Optional[Decimal] = None


# ---- Trust / Financials ----------------------------------------------------
class TrustIO(_CamelModel):
    exists: bool
    address: Optional[str] = None


class FinancialsIO(_CamelModel):
    inflow: Decimal = Decimal("0")
    outflow: Decimal = Decimal("0")
    deductibles: Decimal = Decimal("0")

    @field_validator("inflow", "outflow", "deductibles")
    @classmethod
    def _nonneg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("must be >= 0")
        return v


# ---- Client payloads -------------------------------------------------------
class ClientIn(_CamelModel):
    id: Optional[str] = None
    married: bool
    client1: PersonIn
    client2: Optional[PersonIn] = None
    retirement: dict[str, list[RetirementAccountIn]] = Field(default_factory=dict)
    non_retirement: list[NonRetirementAccountIn] = Field(default_factory=list)
    trust: TrustIO
    liabilities: list[LiabilityIn] = Field(default_factory=list)
    financials: FinancialsIO


class ClientOut(_CamelModel):
    id: str
    married: bool
    client1: PersonOut
    client2: Optional[PersonOut] = None
    retirement: dict[str, list[RetirementAccountOut]]
    non_retirement: list[NonRetirementAccountOut]
    trust: TrustIO
    liabilities: list[LiabilityOut]
    financials: FinancialsIO
    last_report_date: Optional[date] = None


# ---- Calculate / Reports ---------------------------------------------------
class CalculateIn(_CamelModel):
    financials: FinancialsIO
    balances: dict[str, Decimal] = Field(default_factory=dict)
    liabilities: dict[str, Decimal] = Field(default_factory=dict)
    zillow: Optional[Decimal] = Decimal("0")
    private_reserve: Optional[Decimal] = Decimal("0")


class CalcOut(_CamelModel):
    excess: Decimal
    private_reserve_target: Decimal
    private_reserve_balance: Decimal
    c1_retirement: Decimal
    c2_retirement: Decimal
    non_retirement: Decimal
    trust_value: Decimal
    grand_net_worth: Decimal
    liabilities_total: Decimal
    inflow: Decimal
    outflow: Decimal
    deductibles: Decimal


class LastValuesOut(_CamelModel):
    quarter: Optional[str] = None
    balances: dict[str, Decimal] = Field(default_factory=dict)
    liabilities: dict[str, Decimal] = Field(default_factory=dict)
    zillow: Decimal = Decimal("0")
    private_reserve: Decimal = Decimal("0")


class ReportIn(_CamelModel):
    quarter: str
    date: date
    balances: dict[str, Decimal]
    liabilities: dict[str, Decimal] = Field(default_factory=dict)
    zillow: Optional[Decimal] = Decimal("0")
    private_reserve: Decimal
    financials: FinancialsIO


class ReportOut(_CamelModel):
    id: str
    quarter: str
    date: date
    balances: dict[str, Decimal]
    liabilities: dict[str, Decimal]
    zillow: Decimal
    private_reserve: Decimal
    financials: FinancialsIO
    calc: CalcOut
    created_at: datetime


class MissingFieldsError(_CamelModel):
    detail: str = "missing required field_keys"
    missing: list[str]
