/* ============================================================
   app.js — shared helpers for AW Client Report Portal
   Formatting, calc engine (mirrors POST /api/.../calculate),
   chrome (topbar), icons, toasts.
   ============================================================ */
(function () {
  const AW = (window.AW = window.AW || {});

  /* ---------- Currency / number formatting ---------- */
  const fmt = {
    // 1234567.89 -> "1,234,568"
    money(n, opts) {
      n = Number(n) || 0;
      const o = opts || {};
      const sign = n < 0 ? "−$" : (o.sign && n > 0 ? "+$" : "$");
      return sign + Math.abs(Math.round(n)).toLocaleString("en-US");
    },
    moneyCents(n) {
      n = Number(n) || 0;
      return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
    // bare number with thousands separators (no $)
    num(n) { return (Number(n) || 0).toLocaleString("en-US"); },
    pct(n) { return (Number(n) || 0).toFixed(2) + "%"; },
    // parse "1,234,567" / "$1.2m" loosely -> number
    parse(str) {
      if (typeof str === "number") return str;
      if (!str) return 0;
      return Number(String(str).replace(/[^0-9.\-]/g, "")) || 0;
    },
    // live-format an input value as the user types
    liveInput(str) {
      const neg = String(str).trim().startsWith("-");
      const digits = String(str).replace(/[^0-9]/g, "");
      if (!digits) return "";
      return (neg ? "-" : "") + Number(digits).toLocaleString("en-US");
    },
    initials(c) {
      if (!c) return "?";
      return ((c.firstName || "")[0] || "") + ((c.lastName || "")[0] || "");
    },
  };
  AW.fmt = fmt;

  /* ---------- Date helpers ---------- */
  const dates = {
    age(dob) {
      if (!dob) return null;
      const d = new Date(dob + (dob.length === 10 ? "T00:00:00" : ""));
      if (isNaN(d)) return null;
      const now = new Date();
      let a = now.getFullYear() - d.getFullYear();
      const m = now.getMonth() - d.getMonth();
      if (m < 0 || (m === 0 && now.getDate() < d.getDate())) a--;
      return a;
    },
    pretty(d) {
      if (!d) return "—";
      const dt = new Date(d + (String(d).length === 10 ? "T00:00:00" : ""));
      if (isNaN(dt)) return "—";
      return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    },
    quarterOf(d) {
      const dt = d ? new Date(d) : new Date();
      const q = Math.floor(dt.getMonth() / 3) + 1;
      return { q, year: dt.getFullYear(), label: "Q" + q + " " + dt.getFullYear() };
    },
    // most-recently-closed quarter end relative to today
    currentReportingQuarter() {
      const now = new Date();
      let q = Math.floor(now.getMonth() / 3) + 1; // current quarter
      let year = now.getFullYear();
      q -= 1; // report on the last *completed* quarter
      if (q === 0) { q = 4; year -= 1; }
      const endMonth = q * 3; // 3,6,9,12
      const end = new Date(year, endMonth, 0); // last day of that month
      return { q, year, label: "Q" + q + " " + year, date: end.toISOString().slice(0, 10) };
    },
  };
  AW.dates = dates;

  /* ---------- Household helpers ---------- */
  const who = {
    c1Name(c) { return c.client1 ? `${c.client1.firstName} ${c.client1.lastName}` : "—"; },
    c2Name(c) { return c.client2 ? `${c.client2.firstName} ${c.client2.lastName}` : null; },
    displayName(c) {
      const n1 = who.c1Name(c);
      if (c.married && c.client2) {
        const sameLast = c.client1.lastName === c.client2.lastName;
        return sameLast
          ? `${c.client1.firstName} & ${c.client2.firstName} ${c.client1.lastName}`
          : `${n1} & ${who.c2Name(c)}`;
      }
      return n1;
    },
    householdLabel(c) { return c.married ? "Married household" : "Individual"; },
    // flat account list with friendly labels for report entry
    accounts(c) {
      const out = [];
      (c.retirement[1] || []).forEach((a) => out.push(acct(a, 1)));
      (c.retirement[2] || []).forEach((a) => out.push(acct(a, 2)));
      (c.nonRetirement || []).forEach((a) => out.push(acct(a, 0)));
      return out;

      function acct(a, spouse) {
        const cl = spouse === 1 ? c.client1 : spouse === 2 ? c.client2 : null;
        const owner = spouse === 0 ? "Joint / Non-Retirement" : (cl ? cl.firstName : "Client " + spouse);
        const base = a.name ? `${a.name} ${a.type}` : a.type;
        return {
          id: a.id,
          kind: spouse === 0 ? "nonret" : "ret",
          spouse,
          owner,
          label: `${base} Balance`,
          context: spouse === 0 ? "Non-retirement" : `Client ${spouse} · ${cl ? cl.firstName : ""}`,
          last4: a.last4,
          type: a.type,
        };
      }
    },
  };
  AW.who = who;

  /* ---------- Calculation engine ----------
     Mirrors POST /api/clients/{id}/calculate exactly.
     Rules:
       Excess               = Inflow − Outflow
       Private Reserve Tgt  = 6 × monthly expenses + insurance deductibles
       C1 / C2 Ret Total    = Σ client retirement balances
       Non-Retirement Total = Σ non-retirement account balances (trust EXCLUDED)
       Grand Net Worth      = C1 Ret + C2 Ret + Non-Ret + Trust(Zillow)
       Liabilities Total    = Σ liabilities (shown separately, NEVER subtracted)
  --------------------------------------------- */
  function calculate(client, entry) {
    const f = entry.financials || client.financials;
    const inflow = fmt.parse(f.inflow);
    const outflow = fmt.parse(f.outflow);
    const deductibles = fmt.parse(f.deductibles);
    const bal = entry.balances || {};

    let c1 = 0, c2 = 0, nonret = 0;
    (client.retirement[1] || []).forEach((a) => (c1 += fmt.parse(bal[a.id])));
    (client.retirement[2] || []).forEach((a) => (c2 += fmt.parse(bal[a.id])));
    (client.nonRetirement || []).forEach((a) => (nonret += fmt.parse(bal[a.id])));

    const trustValue = client.trust && client.trust.exists ? fmt.parse(entry.zillow) : 0;
    const grand = c1 + c2 + nonret + trustValue;
    const liabilities = (client.liabilities || []).reduce((s, l) => s, 0); // value comes from entry below
    const liabTotal = fmt.parse(entry.liabilitiesTotal) || 0;

    return {
      excess: inflow - outflow,
      privateReserveTarget: 6 * outflow + deductibles,
      privateReserveBalance: fmt.parse(entry.privateReserve),
      c1Retirement: c1,
      c2Retirement: c2,
      nonRetirement: nonret,
      trustValue,
      grandNetWorth: grand,
      liabilitiesTotal: liabTotal,
      inflow, outflow, deductibles,
    };
  }
  AW.calculate = calculate;

  /* ---------- Icons (inline SVG, stroke style) ---------- */
  const I = {
    plus: 'M12 5v14M5 12h14',
    chevR: 'M9 6l6 6-6 6',
    chevL: 'M15 6l-6 6 6 6',
    edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z',
    file: 'M14 3v5h5M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',
    download: 'M12 3v12m0 0l-4-4m4 4l4-4M4 21h16',
    check: 'M20 6L9 17l-5-5',
    user: 'M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
    users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M23 21v-2a4 4 0 0 0-3-3.87M16 3.13A4 4 0 0 1 16 11',
    trash: 'M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6',
    home: 'M3 11l9-8 9 8M5 10v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V10',
    chart: 'M3 3v18h18M7 14l3-4 4 3 5-7',
    calc: 'M9 7h6M9 11h.01M12 11h.01M15 11h.01M9 15h.01M12 15h.01M15 15h.01M7 3h10a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z',
    history: 'M3 12a9 9 0 1 0 3-6.7M3 4v4h4',
    warn: 'M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
    arrowL: 'M19 12H5m6-7l-7 7 7 7',
    copy: 'M9 9V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-4M15 9H6a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-9a1 1 0 0 0-1-1Z',
    bolt: 'M13 2 3 14h7l-1 8 10-12h-7l1-8Z',
    canva: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm2.5 12.8c-1.6 1.3-3.9 1-4.7-.9-.8-1.9.1-4.2 1.9-4.9 1-.4 2-.2 2.3.4.2.5-.1.8-.4.7-.6-.2-1.2-.1-1.6.4-.7.9-.7 2.6 0 3.3.7.6 1.7.3 2.3-.4.3-.4.8-.1.6.4-.1.4-.3.7-.4.9Z',
    lock: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2ZM7 11V7a5 5 0 0 1 10 0v4',
    unlock: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2ZM7 11V7a5 5 0 0 1 9.9-1',
  };
  function icon(name, size) {
    const d = I[name] || "";
    const s = size || 16;
    return `<svg class="ic" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
  }
  AW.icon = icon;

  /* ---------- Top bar / chrome ---------- */
  function topbar(active) {
    const link = (href, label, key) =>
      `<a href="${href}" class="${active === key ? "active" : ""}">${label}</a>`;
    return `
      <div class="topbar">
        <a href="index.html" class="brand" aria-label="AW Portal home">
          <span class="mark">AW</span>
          <span class="name"><b>AW Portal</b><span>Client Reporting</span></span>
        </a>
        <div class="topbar-links">
          ${link("index.html", "Clients", "clients")}
        </div>
        <div class="spacer"></div>
        <span class="userchip"><span class="av">AW</span>Advisor</span>
      </div>`;
  }
  AW.topbar = topbar;

  /* ---------- Toast ---------- */
  function toast(msg, kind) {
    let wrap = document.querySelector(".toast-wrap");
    if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; document.body.appendChild(wrap); }
    const el = document.createElement("div");
    el.className = "toast";
    el.innerHTML = icon(kind === "ok" ? "check" : "file") + "<span>" + msg + "</span>";
    wrap.appendChild(el);
    setTimeout(() => { el.style.transition = "opacity .3s, transform .3s"; el.style.opacity = "0"; el.style.transform = "translateY(6px)"; }, 2600);
    setTimeout(() => el.remove(), 3000);
  }
  AW.toast = toast;

  /* ---------- URL param ---------- */
  AW.param = (k) => new URLSearchParams(location.search).get(k);

  /* ---------- Currency input wiring (thousands separators live) ---------- */
  AW.bindCurrency = function (input, onChange) {
    function handle() {
      const start = input.selectionStart;
      const before = input.value;
      input.value = fmt.liveInput(input.value);
      // keep caret roughly in place when commas shift
      const diff = input.value.length - before.length;
      try { input.setSelectionRange(start + diff, start + diff); } catch (e) {}
      if (onChange) onChange(fmt.parse(input.value));
    }
    input.addEventListener("input", handle);
    return handle;
  };
})();
