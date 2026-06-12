/* ============================================================
   data.js — Mock data store for AW Client Report Portal
   Mirrors the FastAPI /api contract. Persists to localStorage
   so the prototype feels real across the three pages.

   Swap AW.store.* calls for fetch('/api/...') when wiring the
   real backend — the shapes match the documented endpoints.
   ============================================================ */
(function () {
  const KEY = "aw_portal_v2";

  // ---- Reference data ----
  const RETIREMENT_TYPES = ["IRA", "Roth IRA", "401K", "Pension"];
  const NONRET_TYPES = ["Brokerage", "Joint"];
  const LIABILITY_TYPES = ["Mortgage", "Auto Loan"];

  // ---- Seed: 6 HNW households ----
  function seed() {
    return [
      household({
        id: "c-harrington",
        married: true,
        c1: { firstName: "Robert", lastName: "Harrington", dob: "1958-03-14", ssn: "4417" },
        c2: { firstName: "Eleanor", lastName: "Harrington", dob: "1960-09-02", ssn: "2290" },
        ret1: [
          { type: "IRA", last4: "8841", _bal: 1280000 },
          { type: "401K", last4: "1120", _bal: 940000 },
          { type: "Pension", last4: "5567", _bal: 410000 },
        ],
        ret2: [
          { type: "Roth IRA", last4: "3392", _bal: 620000 },
          { type: "IRA", last4: "7714", _bal: 305000 },
        ],
        nonret: [
          { type: "Brokerage", last4: "9001", _bal: 1840000, _name: "Schwab" },
          { type: "Joint", last4: "4420", _bal: 260000, _name: "Joint" },
        ],
        trust: { exists: true, address: "118 Beacon Hill Rd, Greenwich, CT 06830", _zillow: 3450000 },
        liabilities: [{ type: "Mortgage", rate: 3.25, _bal: 412000 }, { type: "Auto Loan", rate: 5.9, _bal: 38000 }],
        fin: { inflow: 41500, outflow: 24000, deductibles: 28000 },
        lastReport: "2026-03-31",
        prevReserve: 152000,
      }),
      household({
        id: "c-nakamura",
        married: true,
        c1: { firstName: "Kenji", lastName: "Nakamura", dob: "1965-11-21", ssn: "1182" },
        c2: { firstName: "Lydia", lastName: "Nakamura", dob: "1967-06-30", ssn: "7741" },
        ret1: [
          { type: "401K", last4: "2231", _bal: 1120000 },
          { type: "Roth IRA", last4: "8890", _bal: 380000 },
        ],
        ret2: [{ type: "IRA", last4: "5512", _bal: 540000 }],
        nonret: [{ type: "Brokerage", last4: "3301", _bal: 970000, _name: "Fidelity" }],
        trust: { exists: false, address: "", _zillow: 0 },
        liabilities: [{ type: "Mortgage", rate: 2.85, _bal: 295000 }],
        fin: { inflow: 33800, outflow: 19500, deductibles: 19000 },
        lastReport: "2026-03-31",
        prevReserve: 96000,
      }),
      household({
        id: "c-okonkwo",
        married: false,
        c1: { firstName: "Adaeze", lastName: "Okonkwo", dob: "1972-01-08", ssn: "6634" },
        c2: null,
        ret1: [
          { type: "IRA", last4: "1199", _bal: 720000 },
          { type: "401K", last4: "4456", _bal: 615000 },
        ],
        ret2: [],
        nonret: [
          { type: "Brokerage", last4: "7788", _bal: 1330000, _name: "Schwab" },
          { type: "Brokerage", last4: "2014", _bal: 410000, _name: "Vanguard" },
        ],
        trust: { exists: true, address: "44 Lakeshore Dr, Austin, TX 78703", _zillow: 1980000 },
        liabilities: [],
        fin: { inflow: 28200, outflow: 14800, deductibles: 12000 },
        lastReport: "2026-03-31",
        prevReserve: 88000,
      }),
      household({
        id: "c-delacroix",
        married: true,
        c1: { firstName: "Henri", lastName: "Delacroix", dob: "1955-07-19", ssn: "9921" },
        c2: { firstName: "Margaux", lastName: "Delacroix", dob: "1957-12-11", ssn: "3308" },
        ret1: [
          { type: "Pension", last4: "6620", _bal: 880000 },
          { type: "IRA", last4: "1145", _bal: 1010000 },
        ],
        ret2: [
          { type: "Roth IRA", last4: "7732", _bal: 455000 },
          { type: "401K", last4: "9980", _bal: 690000 },
        ],
        nonret: [{ type: "Joint", last4: "5540", _bal: 2210000, _name: "Joint Brokerage" }],
        trust: { exists: true, address: "9 Carmel Valley Rd, Carmel, CA 93923", _zillow: 4120000 },
        liabilities: [{ type: "Mortgage", rate: 4.1, _bal: 510000 }, { type: "Auto Loan", rate: 6.4, _bal: 31000 }, { type: "Auto Loan", rate: 5.5, _bal: 27000 }],
        fin: { inflow: 52000, outflow: 31000, deductibles: 35000 },
        lastReport: "2025-12-31",
        prevReserve: 221000,
      }),
      household({
        id: "c-ferraro",
        married: false,
        c1: { firstName: "Sofia", lastName: "Ferraro", dob: "1980-04-25", ssn: "2256" },
        c2: null,
        ret1: [{ type: "Roth IRA", last4: "3380", _bal: 340000 }],
        ret2: [],
        nonret: [{ type: "Brokerage", last4: "1102", _bal: 760000, _name: "Schwab" }],
        trust: { exists: false, address: "", _zillow: 0 },
        liabilities: [{ type: "Auto Loan", rate: 4.9, _bal: 22000 }],
        fin: { inflow: 22500, outflow: 12200, deductibles: 9000 },
        lastReport: null,
        prevReserve: null,
      }),
      household({
        id: "c-whitfield",
        married: true,
        c1: { firstName: "James", lastName: "Whitfield", dob: "1962-10-05", ssn: "8812" },
        c2: { firstName: "Catherine", lastName: "Whitfield", dob: "1963-02-17", ssn: "4471" },
        ret1: [
          { type: "401K", last4: "5523", _bal: 1450000 },
          { type: "IRA", last4: "9087", _bal: 720000 },
        ],
        ret2: [
          { type: "IRA", last4: "3361", _bal: 410000 },
          { type: "Roth IRA", last4: "6648", _bal: 290000 },
        ],
        nonret: [
          { type: "Brokerage", last4: "7240", _bal: 2050000, _name: "Morgan Stanley" },
          { type: "Joint", last4: "8830", _bal: 340000, _name: "Joint" },
        ],
        trust: { exists: true, address: "27 Highland Ave, Wellesley, MA 02481", _zillow: 2760000 },
        liabilities: [{ type: "Mortgage", rate: 3.5, _bal: 364000 }],
        fin: { inflow: 46800, outflow: 27500, deductibles: 31000 },
        lastReport: "2026-03-31",
        prevReserve: 178000,
      }),
    ];
  }

  // Build a full household record + a seeded prior report for "last values".
  function household(o) {
    const ret1 = o.ret1.map((a, i) => ({ id: uid(), spouse: 1, type: a.type, last4: a.last4, name: a._name || null, _bal: a._bal }));
    const ret2 = o.ret2.map((a, i) => ({ id: uid(), spouse: 2, type: a.type, last4: a.last4, name: a._name || null, _bal: a._bal }));
    const nonret = o.nonret.map((a) => ({ id: uid(), type: a.type, last4: a.last4, name: a._name || null, _bal: a._bal }));
    const liabilities = o.liabilities.map((l) => ({ id: uid(), type: l.type, rate: l.rate, _bal: l._bal }));

    const rec = {
      id: o.id,
      married: o.married,
      client1: o.c1,
      client2: o.c2,
      retirement: { 1: ret1.map(strip), 2: ret2.map(strip) },
      nonRetirement: nonret.map(strip),
      trust: { exists: o.trust.exists, address: o.trust.address },
      liabilities: liabilities.map((l) => { const { _bal, ...rest } = l; return rest; }),
      financials: { inflow: o.fin.inflow, outflow: o.fin.outflow, deductibles: o.fin.deductibles },
      lastReportDate: o.lastReport,
      reports: [],
    };

    // seed one historical report (the "previous quarter") to power last-value hints
    if (o.lastReport) {
      const balances = {};
      [...ret1, ...ret2, ...nonret].forEach((a) => (balances[a.id] = a._bal));
      const liabBalances = {};
      liabilities.forEach((l) => { if (l._bal != null) liabBalances[l.id] = l._bal; });
      const zillow = o.trust.exists ? o.trust._zillow : 0;
      rec.reports.push({
        id: "rep-" + o.id + "-prev",
        quarter: quarterLabel(o.lastReport),
        date: o.lastReport,
        balances,
        liabilities: liabBalances,
        zillow,
        privateReserve: o.prevReserve || 0,
        // store the static snapshot used at the time
        financials: { ...rec.financials },
        createdAt: o.lastReport + "T16:00:00Z",
      });
    }
    return rec;

    function strip(a) { const { _bal, ...rest } = a; return rest; }
  }

  function uid() { return "a" + Math.random().toString(36).slice(2, 9); }
  function quarterLabel(d) {
    const dt = new Date(d + "T00:00:00");
    const q = Math.floor(dt.getMonth() / 3) + 1;
    return "Q" + q + " " + dt.getFullYear();
  }

  // ---- Persistence ----
  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    const fresh = { clients: seed() };
    save(fresh);
    return fresh;
  }
  function save(db) { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) {} }
  function db() { return load(); }

  // ---- "API" surface (synchronous mock) ----
  const store = {
    RETIREMENT_TYPES, NONRET_TYPES, LIABILITY_TYPES,

    // GET /api/clients
    listClients() { return db().clients; },

    // GET /api/clients/{id}
    getClient(id) { return db().clients.find((c) => c.id === id) || null; },

    // POST /api/clients  /  PUT /api/clients/{id}
    saveClient(client) {
      const d = db();
      const i = d.clients.findIndex((c) => c.id === client.id);
      if (i >= 0) d.clients[i] = client;
      else { client.id = client.id || "c-" + uid(); d.clients.unshift(client); }
      save(d);
      return client;
    },

    // GET /api/clients/{id}/last-values  → previous quarter balances keyed by account id
    lastValues(id) {
      const c = this.getClient(id);
      if (!c || !c.reports.length) return null;
      const last = c.reports[c.reports.length - 1];
      return { balances: last.balances || {}, liabilities: last.liabilities || {}, zillow: last.zillow || 0, privateReserve: last.privateReserve || 0, quarter: last.quarter };
    },

    // GET /api/clients/{id}/reports
    listReports(id) {
      const c = this.getClient(id);
      return c ? [...c.reports].reverse() : [];
    },
    getReport(rid) {
      for (const c of db().clients) {
        const r = c.reports.find((x) => x.id === rid);
        if (r) return { report: r, client: c };
      }
      return null;
    },

    // POST /api/clients/{id}/reports
    createReport(id, payload) {
      const d = db();
      const c = d.clients.find((x) => x.id === id);
      if (!c) return null;
      const report = {
        id: "rep-" + uid(),
        quarter: payload.quarter,
        date: payload.date,
        balances: payload.balances,
        liabilities: payload.liabilities || {},
        zillow: payload.zillow,
        privateReserve: payload.privateReserve,
        financials: payload.financials,
        calc: payload.calc,
        createdAt: new Date().toISOString(),
      };
      c.reports.push(report);
      c.lastReportDate = payload.date;
      save(d);
      return report;
    },

    // util for the prototype only
    resetDemo() { localStorage.removeItem(KEY); },
  };

  window.AW = window.AW || {};
  window.AW.store = store;
})();
