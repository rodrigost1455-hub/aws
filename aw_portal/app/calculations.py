"""Pure calculation engine for the AW Client Report Portal.

Mirrors `AW.calculate` in static/app.js exactly. No DB imports.
All money is Decimal, quantized to 2 places on output.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping, Optional

CENTS = Decimal("0.01")
ZERO = Decimal("0")


def q(x: Optional[Decimal | int | float | str]) -> Decimal:
    """Quantize to 2 decimal places. None / blank → 0."""
    if x is None or x == "":
        return ZERO
    d = x if isinstance(x, Decimal) else Decimal(str(x))
    return d.quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class AccountRef:
    id: str
    spouse: int  # 1 client1 retirement, 2 client2 retirement, 0 non-retirement


@dataclass(frozen=True)
class CalcInputs:
    accounts: Iterable[AccountRef]
    trust_exists: bool
    financials: Mapping[str, Decimal | int | float | str]
    balances: Mapping[str, Decimal | int | float | str]
    liabilities: Mapping[str, Decimal | int | float | str]
    zillow: Decimal | int | float | str = ZERO
    private_reserve: Decimal | int | float | str = ZERO


@dataclass(frozen=True)
class CalcResult:
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

    def as_dict(self) -> dict:
        return {
            "excess": self.excess,
            "private_reserve_target": self.private_reserve_target,
            "private_reserve_balance": self.private_reserve_balance,
            "c1_retirement": self.c1_retirement,
            "c2_retirement": self.c2_retirement,
            "non_retirement": self.non_retirement,
            "trust_value": self.trust_value,
            "grand_net_worth": self.grand_net_worth,
            "liabilities_total": self.liabilities_total,
            "inflow": self.inflow,
            "outflow": self.outflow,
            "deductibles": self.deductibles,
        }


def calculate(inp: CalcInputs) -> CalcResult:
    inflow = q(inp.financials.get("inflow"))
    outflow = q(inp.financials.get("outflow"))
    deductibles = q(inp.financials.get("deductibles"))

    c1 = ZERO
    c2 = ZERO
    nonret = ZERO
    for a in inp.accounts:
        bal = q(inp.balances.get(a.id))
        if a.spouse == 1:
            c1 += bal
        elif a.spouse == 2:
            c2 += bal
        else:
            # non-retirement — trust value is NEVER included here
            nonret += bal

    trust_value = q(inp.zillow) if inp.trust_exists else ZERO
    grand = c1 + c2 + nonret + trust_value
    liabilities_total = sum((q(v) for v in inp.liabilities.values()), ZERO)

    return CalcResult(
        excess=q(inflow - outflow),
        private_reserve_target=q(Decimal(6) * outflow + deductibles),
        private_reserve_balance=q(inp.private_reserve),
        c1_retirement=q(c1),
        c2_retirement=q(c2),
        non_retirement=q(nonret),
        trust_value=q(trust_value),
        grand_net_worth=q(grand),
        liabilities_total=q(liabilities_total),
        inflow=inflow,
        outflow=outflow,
        deductibles=deductibles,
    )
