# AW Client Report Portal — Backend Build Prompt (Claude Code handoff)

> **How to use:** paste this whole document into Claude Code, with the existing
> frontend files (`index.html`, `client.html`, `report.html`, `styles.css`,
> `report.css`, `app.js`, `client-form.js`, `report.js`, `data.js`) in the repo.
> The frontend is FINISHED and is the source of truth for the API contract.
> Build the backend to match it, then wire the frontend's `data.js` adapter to
> the real API (Part C). Do not redesign the UI.

---

## Part A — What you are building

Backend for the AW Client Report Portal: internal tool, 3 users, ~6–12 clients.

- **Stack:** Python + FastAPI + SQLite (file-based DB on a Railway volume; path
  from env var `RAILWAY_DATABASE_PATH`, default `./data/portal.db`).
  SQLAlchemy ORM + Pydantic v2 schemas. Auto-create tables on startup.
- **Static serving:** the frontend files live at the repo root (or move them to
  `/static`). Mount them so `GET /` serves `index.html` and relative links
  (`client.html`, `report.html`, `styles.css`, …) resolve. Register all `/api`
  routers BEFORE the static mount so the catch-all doesn't shadow the API.
- **No auth in V1**, but isolate request handling so auth middleware can be
  added later (e.g. a single `Depends` placeholder on the routers).
- **Money:** handle as `Decimal` (2 places) internally — never float. JSON
  in/out uses plain numbers.

### Project structure
```
app/
  main.py          # FastAPI app, static mount, router includes
  database.py      # engine/session, env-based path, auto-create
  models.py        # ORM models
  schemas.py       # Pydantic schemas (camelCase JSON via aliases — see Part B)
  calculations.py  # PURE calculation engine (no DB imports)
  routers/
    clients.py
    reports.py
tests/
  test_calculations.py
static/            # the existing frontend files
requirements.txt
```
Start command (Railway): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Data model (ORM — snake_case internally)

- **Client**: `id` (string, e.g. `c-<short>` — see "IDs" below), `married` (bool),
  client1 fields (`first_name`, `last_name`, `dob`, `ssn_last4`), nullable
  client2 fields, `trust_exists` (bool), `trust_property_address` (nullable),
  `monthly_salary` / `monthly_expense_budget` / `insurance_deductibles_total`
  (Decimal), `created_at`, `updated_at`.
- **Account**: `id` (string), `client_id` FK, `owner` (`client1|client2|joint`),
  `category` (`retirement|non_retirement`), `account_type`
  (IRA, Roth IRA, 401K, Pension | Brokerage, Joint), `account_last4`,
  `institution_name` (nullable — the frontend collects a nickname like
  "Schwab" for non-retirement accounts), `sort_order`.
- **Liability**: `id` (string), `client_id` FK, `liability_type`
  (Mortgage, Auto Loan), `interest_rate` (Decimal, nullable).
- **Report**: `id` (string), `client_id` FK, `report_date`, `quarter_label`,
  `financials_snapshot` JSON (inflow/outflow/deductibles used, incl. per-quarter
  overrides), `calc_snapshot` JSON (all totals frozen at generation time),
  `created_at`.
- **ReportEntry**: `id`, `report_id` FK, `field_key` (see key scheme below),
  `value` (Decimal).

Age is computed from DOB at read time, never stored.

> Dropped from the earlier draft: `is_investment` / `cash_value`. The frontend
> does not collect a separate cash balance for investment accounts. Leave the
> `ReportEntry` table generic enough that a `cash:<accountId>` field_key could
> be added later, but do NOT require it anywhere in V1.

### IDs — important
The frontend treats all ids as **opaque strings** and uses account/liability
ids as object keys in report payloads (`balances`, `liabilities`) and in the
last-values response. Therefore:
1. Use short string ids (uuid4 hex slice is fine).
2. **Account and liability ids must be STABLE across `PUT /api/clients/{id}`.**
   On update, match incoming accounts by `id`: update matched rows, create rows
   that arrive without a known id, delete rows that disappeared. If ids are
   regenerated on every save, "last quarter" pre-fill hints break.

### field_key scheme (must match the frontend exactly)
- `bal:<accountId>` — quarter-end balance of an account
- `liab:<liabilityId>` — outstanding liability balance
- `zillow` — Zillow home value (required iff `trust_exists`)
- `reserve` — Private Reserve balance (always required)
- `inflow`, `outflow`, `deductibles` — stored in the report's financials
  snapshot (they arrive in the `financials` object, not as entries; persist
  them both in the snapshot JSON and optionally as entries for queryability)

### Calculation engine — `app/calculations.py` (pure, unit-tested)
EXACT and non-negotiable (the frontend mirrors these in `app.js → AW.calculate`):
1. `excess = inflow - outflow`
2. `private_reserve_target = (6 * monthly_expense_budget) + insurance_deductibles_total`
3. `client1_retirement_total` = Σ client1 retirement balances; same for client2
4. `non_retirement_total` = Σ non-retirement account balances — trust NEVER included
5. `grand_total_net_worth = c1_ret + c2_ret + non_ret + trust_value` — trust IS included
6. `liabilities_total` = Σ liability balances — displayed separately, NEVER subtracted
7. All money as `Decimal`, quantized to 2 places.

pytest coverage: married vs single, trust vs no trust, 0 liabilities, and the
trust-exclusion rule in `non_retirement_total`. Also test that per-quarter
financial overrides (different inflow/outflow than the profile) flow into
`excess` and `private_reserve_target`.

---

## Part B — The JSON contract (source of truth: the existing frontend)

JSON keys are **camelCase** (use Pydantic `alias_generator=to_camel`,
`populate_by_name=True`). The shapes below are exactly what the frontend
already produces/consumes (see `data.js`, `report.js`, `client-form.js`).

### Client object (returned by GET/POST/PUT)
```json
{
  "id": "c-7f3a91",
  "married": true,
  "client1": { "firstName": "Robert", "lastName": "Harrington",
               "dob": "1958-03-14", "ssn": "4417", "age": 68 },
  "client2": { "...same shape, or null": "when single" },
  "retirement": {
    "1": [ { "id": "a-x91k2", "spouse": 1, "type": "IRA",
             "last4": "8841", "name": null } ],
    "2": [ { "id": "a-p20m1", "spouse": 2, "type": "Roth IRA",
             "last4": "3392", "name": null } ]
  },
  "nonRetirement": [
    { "id": "a-q55h8", "type": "Brokerage", "last4": "9001", "name": "Schwab" }
  ],
  "trust": { "exists": true, "address": "118 Beacon Hill Rd, Greenwich, CT 06830" },
  "liabilities": [ { "id": "l-m3n44", "type": "Mortgage", "rate": 3.25 } ],
  "financials": { "inflow": 41500, "outflow": 24000, "deductibles": 28000 },
  "lastReportDate": "2026-03-31"
}
```
`age` is computed server-side at read time. `retirement` keys are the strings
`"1"` and `"2"`. Constraints to validate: 1–6 retirement accounts per spouse,
1–6 non-retirement, 0–3 liabilities, `ssn`/`last4` are exactly 4 digits,
required financials ≥ 0, trust address required when `trust.exists`.

### Endpoints
| Method & path | Behavior |
|---|---|
| `GET /api/clients` | Full nested client objects (≤12 clients — no pagination), each with `lastReportDate`. |
| `POST /api/clients` | Create client with nested accounts + liabilities in one payload (same shape, ids omitted → server assigns). Returns the full object. |
| `GET /api/clients/{id}` | Full profile. 404 if missing. |
| `PUT /api/clients/{id}` | Full update; reconcile accounts/liabilities by id (stable-id rule above). |
| `GET /api/clients/{id}/last-values` | Most recent report's entries, re-keyed for pre-fill (shape below). `null`-equivalent: return 204 or `{"quarter": null, ...empty}` if no reports — frontend handles `null`. |
| `POST /api/clients/{id}/calculate` | Compute totals WITHOUT persisting (request/response below). |
| `POST /api/clients/{id}/reports` | Validate ALL required field_keys present → else **422 with the list of missing field_keys** (e.g. `{"missing": ["bal:a-q55h8", "reserve"]}`). On success: persist Report + ReportEntries + snapshots, return the report object. |
| `GET /api/clients/{id}/reports` | History, newest first. |
| `GET /api/reports/{id}` | Report detail. |
| `GET /api/reports/{id}/pdf?type=sacs\|tcc` | V1: server-rendered PDF via `reportlab` — simple, clean, one page per type: header (household, quarter), the SACS table (financials + asset balances) or TCC table (reserve vs target, liabilities). Structure the renderer so a designed template can replace it later. |
| `POST /api/reports/{id}/export-canva` | Stub: return `501` with `{"detail": "Canva export not configured"}`. |

### `GET /api/clients/{id}/last-values` response
```json
{
  "quarter": "Q1 2026",
  "balances":    { "a-x91k2": 1280000, "a-q55h8": 1840000 },
  "liabilities": { "l-m3n44": 412000 },
  "zillow": 3450000,
  "privateReserve": 152000
}
```

### `POST /api/clients/{id}/calculate` — request
```json
{
  "financials": { "inflow": 41500, "outflow": 24000, "deductibles": 28000 },
  "balances":    { "a-x91k2": 1300000, "a-q55h8": 1900000 },
  "liabilities": { "l-m3n44": 405000 },
  "zillow": 3500000,
  "privateReserve": 160000
}
```
`financials` may differ from the stored profile — these are the per-quarter
**override** values from the UI's lock/override toggles; use them, not the DB
values, for `excess` and `private_reserve_target`.

### `calculate` response / `calc` snapshot (keys must match `AW.calculate` in `app.js`)
```json
{
  "excess": 17500,
  "privateReserveTarget": 172000,
  "privateReserveBalance": 160000,
  "c1Retirement": 2630000,
  "c2Retirement": 925000,
  "nonRetirement": 2100000,
  "trustValue": 3500000,
  "grandNetWorth": 9155000,
  "liabilitiesTotal": 405000,
  "inflow": 41500, "outflow": 24000, "deductibles": 28000
}
```
If the client has no trust, `trustValue` is 0 and `zillow` is ignored.

### `POST /api/clients/{id}/reports` — request (exactly what `report.js` sends)
```json
{
  "quarter": "Q1 2026",
  "date": "2026-03-31",
  "balances":    { "a-x91k2": 1300000 },
  "liabilities": { "l-m3n44": 405000 },
  "zillow": 3500000,
  "privateReserve": 160000,
  "financials": { "inflow": 41500, "outflow": 24000, "deductibles": 28000 }
}
```
(The frontend also sends a client-computed `calc` object — IGNORE it server-side
and recompute via `calculations.py`; the server is authoritative.)

### Report object (response / history rows)
```json
{
  "id": "rep-88ah2",
  "quarter": "Q1 2026",
  "date": "2026-03-31",
  "balances": { "a-x91k2": 1300000 },
  "liabilities": { "l-m3n44": 405000 },
  "zillow": 3500000,
  "privateReserve": 160000,
  "financials": { "inflow": 41500, "outflow": 24000, "deductibles": 28000 },
  "calc": { "...calculate response shape": 0 },
  "createdAt": "2026-06-11T16:02:11Z"
}
```

### Required-fields rule (server must mirror the UI gate)
Required for report creation: `bal:<id>` for EVERY account on the profile,
`liab:<id>` for every liability, `reserve`, and `zillow` iff `trust.exists`.
The UI makes it impossible to submit incomplete data; the server re-validates
and rejects with 422 + the missing key list anyway.

---

## Part C — Wire the existing frontend to the API

The frontend was built with a deliberate seam: **`data.js` exposes `AW.store`**,
a localStorage mock whose method signatures already mirror the endpoints.
Replace its internals with `fetch` calls; keep the rest of the app intact.

1. Rewrite `data.js`: `AW.store.listClients() → GET /api/clients`,
   `getClient`, `saveClient` (POST when no id / PUT when id), `lastValues`,
   `listReports`, `getReport`, `createReport`. Make them **async**, and update
   the call sites in `index.html` (inline script), `client-form.js`, and
   `report.js` to `await` them (each page has one init path — small change).
   Keep `RETIREMENT_TYPES` / `NONRET_TYPES` / `LIABILITY_TYPES` as constants.
2. Delete the localStorage seeding. Add a `scripts/seed.py` (or a
   `POST /api/dev/seed` guarded by an env flag) that loads the same 6 demo
   households so the team can demo against the real backend.
3. Keep `AW.calculate` in `app.js` for the LIVE panel (it must update on every
   keystroke without network chatter). Optionally debounce-call
   `POST /api/clients/{id}/calculate` and console.warn if server and client
   ever disagree — they shouldn't, the rules are identical.
4. Wire the result screen's download buttons to
   `GET /api/reports/{id}/pdf?type=sacs|tcc` (plain `<a href>` is fine) and
   the history table's SACS/TCC buttons likewise. "Export to Canva" calls the
   stub and surfaces the 501 message via the existing `AW.toast`.
5. Frontend dates: the UI computes the reporting quarter (last completed
   quarter) client-side in `AW.dates.currentReportingQuarter()` and sends
   `quarter` + `date` explicitly — the server stores what it receives.

### Acceptance checklist
- [ ] `uvicorn app.main:app` serves the UI at `/` and the API at `/api/*`.
- [ ] Full click-through works against SQLite: add client → edit → generate
      report (all fields) → result + history → re-download PDFs.
- [ ] `pytest` green, including trust-exclusion and override tests.
- [ ] Generating with a missing balance via curl returns 422 listing the keys.
- [ ] Account ids stable across profile edits (last-values still pre-fill).
- [ ] All money round-trips exactly (Decimal, 2 places; no float drift).
