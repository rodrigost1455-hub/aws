"""End-to-end PDF rendering — runs only when WeasyPrint native libs are available."""
from __future__ import annotations

import re

import pytest

from app.pdf_generator import pdf_filename, render_html, render_pdf

from ._pdf_helpers import make_client, make_report, requires_weasyprint


# ---- HTML-only assertions: always run, no native deps required -------------

def test_html_extreme_small_value_renders_without_overflow_class_drift():
    c = make_client(married=True, ret1=2, ret2=2, nonret=2, liabilities=2, trust=True)
    r = make_report(c, balance_per_acct=999, liab_per=999, zillow=999, reserve=999,
                    fin={"inflow": 999, "outflow": 999, "deductibles": 999})
    html_sacs = render_html("sacs", c, r)
    html_tcc = render_html("tcc", c, r)
    # $999 strings should be present, no size-down classes triggered
    assert "$999" in html_sacs
    assert "$999" in html_tcc
    # Confirm fixed-size CSS rules are still emitted — the bubble positions
    # are CSS-only, so they're stable by construction; this catches accidental
    # removal of the constraint classes.
    assert "width: 2.4in" in html_sacs   # bubble size
    assert "width: 1.45in" in html_tcc   # account bubble size


def test_html_extreme_large_value_triggers_sizedown_classes_but_positions_unchanged():
    c = make_client(married=True, ret1=2, ret2=2, nonret=2, liabilities=2, trust=True)
    r = make_report(c, balance_per_acct=99_999_999, liab_per=99_999_999, zillow=99_999_999, reserve=99_999_999,
                    fin={"inflow": 99_999_999, "outflow": 99_999_999, "deductibles": 99_999_999})
    html = render_html("sacs", c, r)
    # The $99,999,999 string is 11 chars (with $) — should hit the "long" class,
    # the cards/bubbles themselves keep their fixed positions.
    assert "$99,999,999" in html
    assert "long" in html  # at least one size-down class triggered
    # No layout properties drift
    assert "width: 2.4in" in html
    # TCC layout still has fixed slots
    html_tcc = render_html("tcc", c, r)
    assert all(f"slot-{i}" in html_tcc or i > 6 for i in range(1, 7))


def _count_markup_slots(html: str, slot: str) -> int:
    # Match class="acct-bubble slot-X" or class="acct-bubble slot-X empty"
    return html.count(f"acct-bubble {slot} empty") + html.count(f'acct-bubble {slot}"')


def test_tcc_single_with_one_account_zero_liabilities_renders_all_slots():
    c = make_client(married=False, ret1=1, ret2=0, nonret=0, liabilities=0, trust=False)
    r = make_report(c)
    html = render_html("tcc", c, r)
    # 6 fixed slots per spouse: 1 filled (c1 slot-1) + 11 empty across the two columns.
    for s in [f"slot-{i}" for i in range(1, 7)]:
        assert _count_markup_slots(html, s) == 2  # one in each spouse column
    assert "No liabilities on file." in html
    assert "Individual household" in html
    assert "None on file" in html  # trust absent


def test_tcc_married_six_six_three_liabilities_with_trust():
    c = make_client(married=True, ret1=6, ret2=6, nonret=6, liabilities=3, trust=True)
    r = make_report(c)
    html = render_html("tcc", c, r)
    # All 6 retirement slots filled per spouse; all 6 non-ret slots filled.
    for i in range(1, 7):
        assert _count_markup_slots(html, f"slot-{i}") == 2
        assert _count_markup_slots(html, f"ns-{i}") == 1
    # All three liabilities pills rendered (count markup, not the CSS rule).
    assert html.count('class="liab-pill"') == 3
    assert "118 Beacon Hill Rd" in html


def test_pdf_filename_is_safe_and_descriptive():
    c = make_client(married=True)
    fn = pdf_filename(c, "sacs", "Q1 2026")
    assert fn == "Robert_and_Eleanor_Harrington_SACS_Q1_2026.pdf"
    fn2 = pdf_filename(make_client(married=False), "tcc", "Q4 2025")
    assert fn2 == "Robert_Harrington_TCC_Q4_2025.pdf"


# ---- Actual PDF renders: skipped if native libs missing --------------------

@requires_weasyprint
def test_pdf_extreme_values_are_byte_deterministic():
    c = make_client(married=True, ret1=6, ret2=6, nonret=6, liabilities=3, trust=True)
    r = make_report(c, balance_per_acct=99_999_999, liab_per=99_999_999, zillow=99_999_999, reserve=99_999_999,
                    fin={"inflow": 99_999_999, "outflow": 99_999_999, "deductibles": 99_999_999})
    a = render_pdf("sacs", c, r)
    b = render_pdf("sacs", c, r)
    assert a == b  # idempotent: history must reproduce identical bytes
    assert a[:4] == b"%PDF"
    # the date-strip succeeded
    assert b"D:19700101000000Z" in a


@requires_weasyprint
def test_pdf_small_values_render_and_are_idempotent():
    c = make_client(married=False, ret1=1, ret2=0, nonret=0, liabilities=0, trust=False)
    r = make_report(c, balance_per_acct=999, fin={"inflow": 999, "outflow": 999, "deductibles": 0})
    a = render_pdf("tcc", c, r)
    b = render_pdf("tcc", c, r)
    assert a == b
    assert a[:4] == b"%PDF"


@requires_weasyprint
def test_pdf_two_pages_for_sacs_one_for_tcc():
    c = make_client()
    r = make_report(c)
    sacs = render_pdf("sacs", c, r)
    tcc = render_pdf("tcc", c, r)
    # crude page count: count "/Type /Page" appearances (excluding /Pages tree)
    def _pages(b: bytes) -> int:
        return len(re.findall(rb"/Type\s*/Page(?!s)", b))
    assert _pages(sacs) == 2
    assert _pages(tcc) == 1
