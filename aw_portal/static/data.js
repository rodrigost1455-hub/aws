/* ============================================================
   data.js — AW Client Report Portal API client
   Replaces the localStorage prototype with real fetch() calls
   against the FastAPI backend. Method shapes match the original
   AW.store surface, but they are now ASYNC (Promise-returning).
   ============================================================ */
(function () {
  const RETIREMENT_TYPES = ["IRA", "Roth IRA", "401K", "Pension"];
  const NONRET_TYPES = ["Brokerage", "Joint"];
  const LIABILITY_TYPES = ["Mortgage", "Auto Loan"];

  async function _req(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (res.status === 204) return null;
    let data = null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      data = await res.json().catch(() => null);
    }
    if (!res.ok) {
      const err = new Error((data && data.detail) || `HTTP ${res.status}`);
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }

  const store = {
    RETIREMENT_TYPES,
    NONRET_TYPES,
    LIABILITY_TYPES,

    listClients() {
      return _req("GET", "/api/clients");
    },

    async getClient(id) {
      try {
        return await _req("GET", "/api/clients/" + encodeURIComponent(id));
      } catch (e) {
        if (e.status === 404) return null;
        throw e;
      }
    },

    // POST when no id / PUT when id is set.
    saveClient(client) {
      if (client.id) {
        return _req("PUT", "/api/clients/" + encodeURIComponent(client.id), client);
      }
      return _req("POST", "/api/clients", client);
    },

    async lastValues(id) {
      const v = await _req("GET", "/api/clients/" + encodeURIComponent(id) + "/last-values");
      if (!v || !v.quarter) return null;
      return v;
    },

    listReports(id) {
      return _req("GET", "/api/clients/" + encodeURIComponent(id) + "/reports");
    },

    async getReport(rid) {
      const r = await _req("GET", "/api/reports/" + encodeURIComponent(rid));
      // The original mock returned {report, client}; the new endpoint only
      // returns the report. Pull the client separately if a caller needs it.
      return r ? { report: r, client: null } : null;
    },

    createReport(id, payload) {
      return _req("POST", "/api/clients/" + encodeURIComponent(id) + "/reports", payload);
    },

    calculate(id, payload) {
      return _req("POST", "/api/clients/" + encodeURIComponent(id) + "/calculate", payload);
    },

    exportCanva(rid) {
      return _req("POST", "/api/reports/" + encodeURIComponent(rid) + "/export-canva");
    },

    pdfUrl(rid, type) {
      return `/api/reports/${encodeURIComponent(rid)}/pdf?type=${encodeURIComponent(type)}`;
    },
  };

  window.AW = window.AW || {};
  window.AW.store = store;
})();
