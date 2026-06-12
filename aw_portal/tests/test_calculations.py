from decimal import Decimal

from app.calculations import AccountRef, CalcInputs, calculate


def D(x):
    return Decimal(str(x))


def _make(accounts, trust_exists=False, **kw):
    return CalcInputs(
        accounts=accounts,
        trust_exists=trust_exists,
        financials=kw.get("financials", {"inflow": 0, "outflow": 0, "deductibles": 0}),
        balances=kw.get("balances", {}),
        liabilities=kw.get("liabilities", {}),
        zillow=kw.get("zillow", 0),
        private_reserve=kw.get("private_reserve", 0),
    )


def test_married_with_trust():
    accts = [
        AccountRef("c1-a", 1),
        AccountRef("c1-b", 1),
        AccountRef("c2-a", 2),
        AccountRef("nr-a", 0),
    ]
    res = calculate(_make(
        accts,
        trust_exists=True,
        financials={"inflow": 41500, "outflow": 24000, "deductibles": 28000},
        balances={"c1-a": 1280000, "c1-b": 940000, "c2-a": 620000, "nr-a": 1840000},
        zillow=3450000,
        private_reserve=152000,
        liabilities={"l1": 412000, "l2": 38000},
    ))
    assert res.excess == D("17500.00")
    assert res.private_reserve_target == D(6 * 24000 + 28000).quantize(D("0.01"))
    assert res.c1_retirement == D("2220000.00")
    assert res.c2_retirement == D("620000.00")
    assert res.non_retirement == D("1840000.00")  # trust NEVER in non-ret
    assert res.trust_value == D("3450000.00")
    assert res.grand_net_worth == D(2220000 + 620000 + 1840000 + 3450000).quantize(D("0.01"))
    assert res.liabilities_total == D("450000.00")
    assert res.private_reserve_balance == D("152000.00")


def test_single_no_trust():
    accts = [AccountRef("a1", 1), AccountRef("nr1", 0)]
    res = calculate(_make(
        accts,
        trust_exists=False,
        financials={"inflow": 22500, "outflow": 12200, "deductibles": 9000},
        balances={"a1": 340000, "nr1": 760000},
        zillow=999999,  # should be ignored
        private_reserve=18000,
    ))
    assert res.trust_value == D("0.00")
    assert res.grand_net_worth == D("1100000.00")
    assert res.excess == D("10300.00")
    assert res.private_reserve_target == D(6 * 12200 + 9000).quantize(D("0.01"))


def test_zero_liabilities():
    res = calculate(_make([AccountRef("a", 1)], balances={"a": 100}, liabilities={}))
    assert res.liabilities_total == D("0.00")


def test_trust_excluded_from_non_retirement():
    accts = [AccountRef("nr1", 0), AccountRef("nr2", 0)]
    res = calculate(_make(
        accts,
        trust_exists=True,
        balances={"nr1": 500000, "nr2": 250000},
        zillow=2000000,
    ))
    assert res.non_retirement == D("750000.00")
    # grand_net_worth picks up trust separately
    assert res.grand_net_worth == D("2750000.00")


def test_per_quarter_overrides_drive_excess_and_target():
    # profile financials would yield excess=10k, target=6*5000+0=30k
    # but quarter overrides should win
    res = calculate(_make(
        [AccountRef("a", 1)],
        financials={"inflow": 50000, "outflow": 20000, "deductibles": 10000},
        balances={"a": 100000},
        private_reserve=80000,
    ))
    assert res.excess == D("30000.00")
    assert res.private_reserve_target == D(6 * 20000 + 10000).quantize(D("0.01"))
    assert res.private_reserve_balance == D("80000.00")


def test_money_round_trips_two_places():
    res = calculate(_make(
        [AccountRef("a", 0)],
        balances={"a": "123456.789"},
        liabilities={"l": "1.005"},
        financials={"inflow": "100.005", "outflow": "50.004", "deductibles": "0.0"},
    ))
    # HALF_UP rounding
    assert str(res.non_retirement) == "123456.79"
    assert str(res.liabilities_total) == "1.01"
    assert str(res.inflow) == "100.01"
    assert str(res.outflow) == "50.00"
