# AW Client Report Portal

Internal advisor tool for generating quarterly **SACS** (Simple Automated Cash
Flow) and **TCC** (Total Client Chart) reports for high-net-worth households.
Three users, ~6–12 clients, single Railway container.

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2
- **PDFs:** Jinja2 templates → WeasyPrint (HTML/CSS → PDF), absolutely
  positioned so layouts never reflow regardless of number length
- **Frontend:** static HTML/CSS/JS
- **Deploy:** Dockerfile based on `python:3.12-slim`, mounted SQLite volume

---

## Quick start (local)

```bash
cd aw_portal
pip install -r requirements.txt

# WeasyPrint needs Pango/Cairo at runtime — install the matching system libs:
#   macOS:    brew install pango libffi gdk-pixbuf
#   Debian:   sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 \
#                                  libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0
#   Windows:  install MSYS2, then `pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-cairo`
#             and add C:\msys64\mingw64\bin to PATH

python -m scripts.seed                       # load 6 demo households
python -m uvicorn app.main:app --reload      # serve UI + API at http://localhost:8000
```

> **Windows port note.** Port 8000 is often inside Windows' Hyper-V excluded
> range and will fail with `WinError 10013`. Pick another port:
> `python -m uvicorn app.main:app --reload --port 8765`.

If WeasyPrint can't load its native libs, the **preview endpoint**
(`GET /api/reports/{id}/preview?type=sacs|tcc`) still returns the raw HTML and
is the recommended path for iterating on templates.

---

## Project layout

```
aw_portal/
├── app/
│   ├── main.py             # FastAPI app, static mount, router includes
│   ├── database.py         # engine/session, RAILWAY_DATABASE_PATH, auto-create
│   ├── models.py           # SQLAlchemy ORM (Client, Account, Liability, Report, ReportEntry)
│   ├── schemas.py          # Pydantic v2 (camelCase via to_camel)
│   ├── calculations.py     # pure Decimal calc engine (mirrors AW.calculate)
│   ├── crud.py             # stable-id reconciliation, last-values, calc glue
│   ├── pdf_generator.py    # Jinja2 + WeasyPrint render, deterministic output
│   ├── canva.py            # Canva Connect client, env-var gated
│   ├── ids.py              # opaque short string ids
│   ├── auth.py             # placeholder Depends for V2 auth
│   └── routers/
│       ├── clients.py      # /api/clients/*
│       └── reports.py      # /api/clients/{id}/reports, /api/reports/{id}/*
├── templates/
│   ├── sacs.html           # 2-page bubble cashflow + reserve detail
│   └── tcc.html            # 1-page client chart with fixed slot grid
├── static/                 # prototype HTML/CSS/JS rewired to fetch /api
├── scripts/seed.py         # load 6 demo households, idempotent
├── tests/                  # pytest: calc, API, PDF render, Canva
├── data/portal.db          # runtime SQLite (gitignored)
├── Dockerfile              # python:3.12-slim + Pango/Cairo
├── DEPLOY.md               # Railway deploy notes + Windows install
├── pytest.ini
└── requirements.txt

design_handoff/             # original Claude Design bundle (README, chats, prototype)
```

---

## Configuration

All optional, set via environment variables:

| Var | Default | Purpose |
|---|---|---|
| `RAILWAY_DATABASE_PATH` | `./data/portal.db` | SQLite file location |
| `CANVA_API_KEY` | — | Activates `POST /api/reports/{id}/export-canva`; absent → 501 |
| `CANVA_API_BASE` | `https://api.canva.com/rest/v1` | Override for staging/proxies |
| `AW_DEV_SEED` | — | When `=1`, seeds demo households on startup if DB is empty |
| `AW_ALLOW_DEV_SEED` | — | When `=1`, exposes `POST /api/dev/seed` (leave unset in prod) |
| `PORT` | `8000` | Bound by the start command |

---

## API surface

All JSON in/out is **camelCase**. Money is `Decimal(2)` server-side, plain
numbers on the wire.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/clients` | Full nested objects, each with `lastReportDate` |
| `POST` | `/api/clients` | Create with nested accounts + liabilities |
| `GET` | `/api/clients/{id}` | Full profile, 404 if missing |
| `PUT` | `/api/clients/{id}` | Full update — reconciles by id (stable) |
| `GET` | `/api/clients/{id}/last-values` | Previous-quarter values, re-keyed for pre-fill |
| `POST` | `/api/clients/{id}/calculate` | Compute totals without persisting |
| `POST` | `/api/clients/{id}/reports` | 422 + missing field_key list on incomplete data |
| `GET` | `/api/clients/{id}/reports` | History, newest first |
| `GET` | `/api/reports/{id}` | Report detail |
| `GET` | `/api/reports/{id}/pdf?type=sacs\|tcc` | Server-rendered PDF, deterministic bytes |
| `GET` | `/api/reports/{id}/preview?type=sacs\|tcc` | Raw HTML for template iteration |
| `POST` | `/api/reports/{id}/export-canva` | Uploads PDFs to Canva when `CANVA_API_KEY` is set, otherwise 501 |

### Calculation rules

The engine is pure and unit-tested. The frontend `AW.calculate` mirrors it.

```
excess                  = inflow - outflow
private_reserve_target  = 6 * outflow + insurance_deductibles
c1_retirement_total     = Σ client1 retirement balances
c2_retirement_total     = Σ client2 retirement balances
non_retirement_total    = Σ non-retirement balances        # trust NEVER included
grand_total_net_worth   = c1_ret + c2_ret + non_ret + trust_value
liabilities_total       = Σ liability balances              # shown separately, never subtracted
```

### `field_key` scheme (used in `ReportEntry`)

- `bal:<accountId>` — quarter-end account balance
- `liab:<liabilityId>` — outstanding liability balance
- `zillow` — trust property value (required iff `trust.exists`)
- `reserve` — Private Reserve balance (always required)
- `inflow`, `outflow`, `deductibles` — financial snapshot fields

---

## PDF design

Both layouts are absolute-positioned. **Number length cannot shift anything** —
oversized values just drop into smaller font classes within their fixed boxes.

- **SACS** (2 pages, Letter)
  - Page 1: header → green Inflow circle → red arrow with X marker → red
    Outflow circle → blue Excess arrow → blue Private Reserve card
  - Page 2: Reserve balance + Reserve Target stat cards, non-retirement
    investment account rows
- **TCC** (1 page, Letter)
  - Green client info bubbles per spouse
  - Fixed 6-slot retirement grid per spouse (empty slots render as dashed
    placeholders so the grid never reflows)
  - Fixed 6-slot non-retirement grid
  - Amber Trust card with Zillow estimate
  - Liabilities pill row (informational, never subtracted)
  - Four summary boxes: C1 Retirement / C2 Retirement / Non-Retirement /
    Grand Total Net Worth (blue)

Renders are pure functions of the frozen `calc_snapshot` on the Report record
— **history reproduces byte-identical PDFs**. The volatile PDF creation date
is stripped to keep the output deterministic.

---

## Testing

```bash
cd aw_portal
python -m pytest -q
```

What's covered:

- **`test_calculations.py`** — married/single, trust/no-trust, 0 liabilities,
  trust-exclusion in non-retirement, per-quarter overrides, Decimal rounding
- **`test_api.py`** — stable account/liability ids across `PUT`, 422 with
  missing field_keys, full report-create + preview, last-values pre-fill,
  Canva 501
- **`test_pdf_render.py`** — extreme values ($999 and $99,999,999) prove
  layout doesn't drift; TCC single+1 acct+0 liabs and married+6+6+trust+3
  liabs edge cases; PDF page counts; deterministic byte output
- **`test_canva.py`** — env-var gating, mocked Canva Connect upload, design
  failure still returns the asset, 401 maps to `CanvaError`

The 3 actual-PDF-render tests skip cleanly when WeasyPrint native libs are
unavailable (e.g. Windows without MSYS2). The full suite runs green in the
Docker image.

---

## Deploy

https://awssagan.up.railway.app/index.html

---

## License

Internal — not for redistribution.
