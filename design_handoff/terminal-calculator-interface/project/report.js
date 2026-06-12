/* ============================================================
   report.js — Quarterly Report Data Entry + Live Calc + Result
   - SACS section (static financials + asset balances + Zillow)
   - TCC section (deductibles, Private Reserve, liability balances)
   - Static fields read-only-by-default with override toggle
   - Dynamic fields with last-quarter hints + "Use last value"
   - 3 calc-panel placements: sidebar / pinned dock / top cards
   - Generate stays disabled until every required field is filled
   ============================================================ */
(function () {
  document.getElementById("chrome").innerHTML = AW.topbar("clients");

  const T = AW.store;
  const id = AW.param("id");
  const client = id ? T.getClient(id) : null;
  const root = document.getElementById("reportRoot");

  /* ---------- guard: no client ---------- */
  if (!client) {
    document.getElementById("vbar").style.display = "none";
    root.innerHTML = `<div class="section"><div class="empty">
      <div>${AW.icon("warn", 40)}</div>
      <h4>No client selected</h4>
      <p>Pick a household from the client list to generate its quarterly report.</p>
      <p style="margin-top:14px"><a class="btn btn-primary" href="index.html">${AW.icon("arrowL", 14)} Back to clients</a></p>
    </div></div>`;
    return;
  }

  const RQ = AW.dates.currentReportingQuarter();
  const lastVals = T.lastValues(client.id); // {balances, zillow, privateReserve, quarter} | null
  const accounts = AW.who.accounts(client);

  /* ---------- header ---------- */
  const name = AW.who.displayName(client);
  document.title = "Report · " + name + " · AW Portal";
  const crumb = document.getElementById("crumbClient");
  crumb.textContent = name;
  crumb.href = "client.html?id=" + client.id;
  document.getElementById("eyebrow").textContent = RQ.label + " quarterly report";
  document.getElementById("title").textContent = name;
  document.getElementById("sub").innerHTML =
    `${AW.who.householdLabel(client)} · ${accounts.length} accounts` +
    (client.trust.exists ? " · Trust" : "") +
    (lastVals ? ` · previous report <b>${lastVals.quarter}</b>` : " · first report");
  document.getElementById("headTools").innerHTML =
    `<a class="btn btn-ghost" href="client.html?id=${client.id}">${AW.icon("edit", 14)} Edit Profile</a>`;

  /* ---------- dynamic field model ---------- */
  const dynFields = [];
  accounts.forEach((a) => {
    dynFields.push({
      key: "bal:" + a.id,
      section: "sacs",
      label: a.label,
      ctx: `${a.context} · ····${a.last4}`,
      pill: a.spouse === 1 ? "c1" : a.spouse === 2 ? "c2" : "nr",
      pillText: a.spouse === 1 ? "C1" : a.spouse === 2 ? "C2" : "NON-RET",
      group: a.spouse === 1 ? "ret1" : a.spouse === 2 ? "ret2" : "nonret",
      last: lastVals && lastVals.balances[a.id] != null ? lastVals.balances[a.id] : null,
    });
  });
  if (client.trust.exists) {
    dynFields.push({
      key: "zillow", section: "sacs", group: "trust",
      label: "Zillow Home Value",
      ctx: client.trust.address || "Trust property",
      pill: "tr", pillText: "TRUST",
      last: lastVals ? lastVals.zillow : null,
    });
  }
  dynFields.push({
    key: "reserve", section: "tcc", group: "reserve",
    label: "Private Reserve Balance",
    ctx: "Current balance of the reserve account",
    pill: "rs", pillText: "RESERVE",
    last: lastVals && lastVals.privateReserve != null ? lastVals.privateReserve : null,
  });
  (client.liabilities || []).forEach((l, i) => {
    dynFields.push({
      key: "liab:" + l.id, section: "tcc", group: "liab",
      label: l.type + " Balance",
      ctx: (l.rate != null ? l.rate + "% interest" : "Liability") + " · shown separately",
      pill: "", pillText: "LIAB",
      last: lastVals && lastVals.liabilities && lastVals.liabilities[l.id] != null ? lastVals.liabilities[l.id] : null,
    });
  });

  /* ---------- state ---------- */
  const entries = {};                     // key -> number | ""
  dynFields.forEach((f) => (entries[f.key] = ""));
  const fin = {                           // static, overridable
    inflow: Number(client.financials.inflow) || 0,
    outflow: Number(client.financials.outflow) || 0,
    deductibles: Number(client.financials.deductibles) || 0,
  };
  const overridden = { inflow: false, outflow: false, deductibles: false };
  let layout = localStorage.getItem("aw_layout") || "sidebar";
  let generated = null;                   // report object after creation

  /* ---------- tiny html helpers ---------- */
  const esc = (s) => String(s == null ? "" : s).replace(/</g, "&lt;").replace(/"/g, "&quot;");

  function bfieldHtml(f) {
    const v = entries[f.key];
    const has = v !== "" && v != null;
    const lastRow =
      f.last != null
        ? `<span class="lasthint">Last quarter <b>${AW.fmt.money(f.last)}</b></span>
           <button type="button" class="uselast" data-uselast="${f.key}">${AW.icon("history", 12)} Use last value</button>
           <span class="delta" data-delta="${f.key}"></span>`
        : `<span class="lasthint" style="color:var(--muted-2)">No prior value on file</span>`;
    return `<div class="bfield ${has ? "filled" : ""}" data-bfield="${f.key}">
      <div class="head">
        <span class="pill ${f.pill}">${f.pillText}</span>
        <div class="meta">
          <div class="label">${esc(f.label)}</div>
          <div class="ctx">${esc(f.ctx)}</div>
        </div>
        <span class="check">${AW.icon("check", 16)}</span>
      </div>
      <div class="input-affix"><span class="affix">$</span>
        <input class="input" inputmode="numeric" placeholder="0" data-key="${f.key}" value="${has ? AW.fmt.num(v) : ""}" />
      </div>
      <div class="lastrow">${lastRow}</div>
    </div>`;
  }

  function sfieldHtml(key, label, sub) {
    return `<div class="sfield" data-sfield="${key}">
      <div class="top">
        <span class="lbl">${label}</span>
        <span class="ovr-tag" data-ovr style="display:none">OVERRIDDEN</span>
        <button type="button" class="lockbtn" data-lock="${key}">${AW.icon("lock", 12)} <span>Override</span></button>
      </div>
      <div class="val" data-sval>${AW.fmt.money(fin[key])}</div>
      <div class="editrow">
        <div class="input-affix"><span class="affix">$</span>
          <input class="input" inputmode="numeric" data-skey="${key}" value="${AW.fmt.num(fin[key])}" />
        </div>
      </div>
      <span class="section-desc">${sub}</span>
    </div>`;
  }

  function secProgHtml(sec) {
    return `<span class="prog" data-secprog="${sec}">
      <span class="bar"><span style="width:0%"></span></span>
      <span data-secprog-text>0/0</span>
    </span>`;
  }

  /* ---------- form sections ---------- */
  function groupBlock(title, fields) {
    if (!fields.length) return "";
    return `<div style="margin-bottom:4px">
      <div class="calc-group-label" style="padding:6px 0 8px">${title}</div>
      <div class="entry-grid">${fields.map(bfieldHtml).join("")}</div>
    </div>`;
  }

  function formHtml() {
    const c1First = client.client1.firstName;
    const c2First = client.client2 ? client.client2.firstName : "Client 2";
    const sacs = dynFields.filter((f) => f.section === "sacs");
    const tcc = dynFields.filter((f) => f.section === "tcc");

    const roster = accounts
      .map((a) => `<span class="tag">${esc(a.type)} ····${a.last4}</span>`)
      .join(" ");

    return `
    <!-- SACS ------------------------------------------------------>
    <section class="section report-section">
      <div class="section-head">
        <span class="sacs-badge">SACS</span>
        <h3>Asset &amp; cash-flow statement</h3>
        <span class="hint">Static data carried from profile + quarter-end balances</span>
        <div class="spacer"></div>
        ${secProgHtml("sacs")}
      </div>
      <div class="section-body">
        <div class="calc-group-label" style="padding:0 0 8px">Static — pre-filled from profile</div>
        <div class="entry-grid" style="margin-bottom:6px">
          ${sfieldHtml("inflow", "Monthly salary, after tax (Inflow)", "Read-only · toggle Override for a one-off correction")}
          ${sfieldHtml("outflow", "Agreed monthly expense budget (Outflow)", "Used for Excess and the Private Reserve Target")}
        </div>
        <div class="row row-wrap gap-sm" style="margin-bottom:14px">
          <span class="section-desc">Accounts on file:</span> ${roster}
        </div>
        ${groupBlock("Retirement — " + esc(c1First) + " (Client 1)", sacs.filter((f) => f.group === "ret1"))}
        ${client.married ? groupBlock("Retirement — " + esc(c2First) + " (Client 2)", sacs.filter((f) => f.group === "ret2")) : ""}
        ${groupBlock("Non-retirement accounts", sacs.filter((f) => f.group === "nonret"))}
        ${groupBlock("Trust property", sacs.filter((f) => f.group === "trust"))}
      </div>
    </section>

    <!-- TCC ------------------------------------------------------->
    <section class="section report-section">
      <div class="section-head">
        <span class="tcc-badge">TCC</span>
        <h3>Reserve &amp; liabilities</h3>
        <span class="hint">Private reserve coverage and outstanding balances</span>
        <div class="spacer"></div>
        ${secProgHtml("tcc")}
      </div>
      <div class="section-body">
        <div class="calc-group-label" style="padding:0 0 8px">Static — pre-filled from profile</div>
        <div class="entry-grid" style="margin-bottom:14px">
          ${sfieldHtml("deductibles", "Sum of insurance deductibles", "Feeds the Private Reserve Target: (6 × Outflow) + deductibles")}
        </div>
        ${groupBlock("Private reserve", tcc.filter((f) => f.group === "reserve"))}
        ${groupBlock("Liabilities — informational, never subtracted", tcc.filter((f) => f.group === "liab"))}
      </div>
    </section>`;
  }

  /* ---------- calc panel variants ---------- */
  function panelHtml() {
    return `<div class="calc">
      <div class="calc-head">${AW.icon("calc", 16)}<h3>Live calculation</h3>
        <span class="live"><span class="blip"></span>LIVE</span></div>
      <div class="calc-body">
        <div class="cline"><span class="k">Excess<span class="sub">Inflow − Outflow</span></span><span class="v" data-calc="excess">$0</span></div>
        <div class="cline"><span class="k">Private Reserve Target<span class="sub">(6 × Outflow) + deductibles</span></span><span class="v" data-calc="reserveTarget">$0</span></div>
        <div class="cline"><span class="k">Private Reserve Balance</span><span class="v" data-calc="reserveBalance">$0</span></div>
        <div class="gauge">
          <div class="bar"><span data-gauge-bar style="width:0%;background:var(--blue-600)"></span></div>
          <div class="row"><span data-gauge-label>Reserve funding</span><span data-gauge-pct>—</span></div>
        </div>
        <div class="calc-group-label">Net worth build-up</div>
        <div class="cline sub-line"><span class="k">Client 1 retirement</span><span class="v" data-calc="c1ret">$0</span></div>
        ${client.married ? `<div class="cline sub-line"><span class="k">Client 2 retirement</span><span class="v" data-calc="c2ret">$0</span></div>` : ""}
        <div class="cline sub-line"><span class="k">Non-retirement<span class="sub">accounts only — trust excluded</span></span><span class="v" data-calc="nonret">$0</span></div>
        ${client.trust.exists ? `<div class="cline sub-line"><span class="k">Trust (Zillow)</span><span class="v" data-calc="trust">$0</span></div>` : ""}
        <div class="cline total"><span class="k">Grand Total Net Worth</span><span class="v" data-calc="grand">$0</span></div>
        <div class="cline"><span class="k">Liabilities Total<span class="sub">shown separately — never subtracted</span></span><span class="v" data-calc="liab">$0</span></div>
        <div class="calc-note">${AW.icon("bolt", 14)}<span>Mirrors <code>POST /api/clients/${client.id}/calculate</code> — server re-validates on generate.</span></div>
      </div>
      <div class="calc-cta">
        <button class="btn btn-primary btn-block" data-gen disabled>${AW.icon("chart", 15)} Generate ${RQ.label} report</button>
        <div class="why" data-why></div>
      </div>
    </div>`;
  }

  function cardsHtml() {
    return `<div class="calc-cards">
      <div class="ccard"><div class="k">Monthly Excess</div><div class="v" data-calc="excess">$0</div><div class="s">Inflow − Outflow</div></div>
      <div class="ccard accent"><div class="k">Grand Total Net Worth</div><div class="v" data-calc="grand">$0</div><div class="s">C1 + C2 + Non-ret + Trust</div></div>
      <div class="ccard"><div class="k">Private Reserve</div><div class="v" data-calc="reserveBalance">$0</div><div class="s"><span data-gauge-label>vs target</span> · <span data-gauge-pct>—</span></div></div>
      <div class="ccard"><div class="k">Liabilities Total</div><div class="v" data-calc="liab">$0</div><div class="s">Never subtracted</div></div>
      <div class="calc-cards-foot">
        <span class="prog"><span class="bar"><span data-prog-bar style="width:0%"></span></span><span data-prog-text>0/0 fields</span></span>
        <div class="spacer" style="flex:1"></div>
        <span class="why" data-why style="margin:0"></span>
        <button class="btn btn-primary" data-gen disabled>${AW.icon("chart", 15)} Generate ${RQ.label} report</button>
      </div>
    </div>`;
  }

  function dockHtml() {
    return `<div class="calc-dock"><div class="inner">
      <div class="dock-stat"><span class="k">Excess</span><span class="v" data-calc="excess">$0</span></div>
      <div class="dock-divider"></div>
      <div class="dock-stat opt"><span class="k">C1 Retirement</span><span class="v" data-calc="c1ret">$0</span></div>
      ${client.married ? `<div class="dock-stat opt"><span class="k">C2 Retirement</span><span class="v" data-calc="c2ret">$0</span></div>` : ""}
      <div class="dock-stat opt"><span class="k">Non-Ret</span><span class="v" data-calc="nonret">$0</span></div>
      ${client.trust.exists ? `<div class="dock-stat opt"><span class="k">Trust</span><span class="v" data-calc="trust">$0</span></div>` : ""}
      <div class="dock-divider"></div>
      <div class="dock-stat"><span class="k">Grand Net Worth</span><span class="v grand" data-calc="grand">$0</span></div>
      <div class="dock-stat opt"><span class="k">Liabilities</span><span class="v" data-calc="liab">$0</span></div>
      <div class="spacer"></div>
      <div class="dock-prog">
        <span class="lbl" data-prog-text>0/0 fields</span>
        <span class="prog"><span class="bar"><span data-prog-bar style="width:0%"></span></span></span>
      </div>
      <button class="btn btn-primary" data-gen disabled>${AW.icon("chart", 15)} Generate</button>
    </div></div>`;
  }

  /* ---------- entry view ---------- */
  function renderEntry() {
    document.getElementById("vbar").style.display = "";
    let html = "";
    if (layout === "sidebar") {
      html = `<div class="layout-sidebar">
        <div>${formHtml()}</div>
        <div class="calc-host">${panelHtml()}</div>
      </div>`;
    } else if (layout === "top") {
      html = `<div class="layout-top">
        <div class="calc-host">${cardsHtml()}</div>
        ${formHtml()}
      </div>`;
    } else {
      html = `<div class="layout-bottom">${formHtml()}${dockHtml()}</div>`;
    }
    root.innerHTML = html;
    wire();
    updateCalc();
  }

  /* ---------- wiring ---------- */
  function wire() {
    // dynamic balance inputs
    root.querySelectorAll("[data-key]").forEach((inp) => {
      AW.bindCurrency(inp, (v) => {
        entries[inp.dataset.key] = inp.value === "" ? "" : v;
        updateCalc();
      });
    });
    // use-last buttons
    root.querySelectorAll("[data-uselast]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.uselast;
        const f = dynFields.find((x) => x.key === key);
        entries[key] = f.last;
        const inp = root.querySelector(`[data-key="${CSS.escape(key)}"]`);
        inp.value = AW.fmt.num(f.last);
        updateCalc();
      });
    });
    // static override toggles
    root.querySelectorAll("[data-lock]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.lock;
        const box = btn.closest(".sfield");
        const unlocked = box.classList.toggle("unlocked");
        btn.innerHTML = (unlocked ? AW.icon("unlock", 12) : AW.icon("lock", 12)) +
          `<span>${unlocked ? "Lock" : "Override"}</span>`;
        if (!unlocked) {
          // re-lock: keep override value, just collapse editor
          box.querySelector("[data-sval]").textContent = AW.fmt.money(fin[key]);
        }
      });
    });
    root.querySelectorAll("[data-skey]").forEach((inp) => {
      const key = inp.dataset.skey;
      AW.bindCurrency(inp, (v) => {
        fin[key] = v;
        overridden[key] = v !== (Number(client.financials[key]) || 0);
        const box = inp.closest(".sfield");
        box.querySelector("[data-ovr]").style.display = overridden[key] ? "" : "none";
        updateCalc();
      });
    });
    // generate buttons
    root.querySelectorAll("[data-gen]").forEach((btn) => btn.addEventListener("click", generate));
  }

  /* ---------- live calculation ---------- */
  function calcNow() {
    const balances = {};
    Object.keys(entries).forEach((k) => { if (k.startsWith("bal:")) balances[k.slice(4)] = entries[k]; });
    const liabTotal = Object.keys(entries)
      .filter((k) => k.startsWith("liab:"))
      .reduce((s, k) => s + AW.fmt.parse(entries[k]), 0);
    return AW.calculate(client, {
      financials: fin,
      balances,
      zillow: entries.zillow,
      privateReserve: entries.reserve,
      liabilitiesTotal: liabTotal,
    });
  }

  function updateCalc() {
    const c = calcNow();
    const filled = dynFields.filter((f) => entries[f.key] !== "" && entries[f.key] != null);
    const started = filled.length > 0;
    const complete = filled.length === dynFields.length;

    // values
    const map = {
      excess: AW.fmt.money(c.excess, { sign: true }),
      reserveTarget: AW.fmt.money(c.privateReserveTarget),
      reserveBalance: AW.fmt.money(c.privateReserveBalance),
      c1ret: AW.fmt.money(c.c1Retirement),
      c2ret: AW.fmt.money(c.c2Retirement),
      nonret: AW.fmt.money(c.nonRetirement),
      trust: AW.fmt.money(c.trustValue),
      grand: AW.fmt.money(c.grandNetWorth),
      liab: AW.fmt.money(c.liabilitiesTotal),
    };
    root.querySelectorAll("[data-calc]").forEach((el) => {
      const k = el.dataset.calc;
      el.textContent = map[k] || "$0";
      if (k === "excess") el.classList.toggle("pos", c.excess > 0), el.classList.toggle("neg", c.excess < 0);
    });

    // reserve gauge
    const pct = c.privateReserveTarget > 0 ? (c.privateReserveBalance / c.privateReserveTarget) * 100 : 0;
    root.querySelectorAll("[data-gauge-bar]").forEach((el) => {
      el.style.width = Math.min(100, pct) + "%";
      el.style.background = pct >= 100 ? "var(--green-600)" : pct >= 60 ? "var(--blue-600)" : "var(--amber-500)";
    });
    root.querySelectorAll("[data-gauge-pct]").forEach((el) => (el.textContent = entries.reserve === "" ? "—" : Math.round(pct) + "% of target"));
    root.querySelectorAll("[data-gauge-label]").forEach((el) =>
      (el.textContent = pct >= 100 ? "Target met" : "Reserve funding"));

    // field states (red only after entry has begun)
    dynFields.forEach((f) => {
      const el = root.querySelector(`[data-bfield="${CSS.escape(f.key)}"]`);
      if (!el) return;
      const has = entries[f.key] !== "" && entries[f.key] != null;
      el.classList.toggle("filled", has);
      el.classList.toggle("missing", !has && started);
      // delta vs last
      const d = el.querySelector("[data-delta]");
      if (d && f.last != null) {
        if (has && f.last !== 0) {
          const diff = entries[f.key] - f.last;
          d.textContent = (diff >= 0 ? "▲ " : "▼ ") + AW.fmt.money(Math.abs(diff));
          d.className = "delta " + (diff >= 0 ? "up" : "down");
        } else d.textContent = "";
      }
    });

    // per-section progress
    ["sacs", "tcc"].forEach((sec) => {
      const secFields = dynFields.filter((f) => f.section === sec);
      const secFilled = secFields.filter((f) => entries[f.key] !== "").length;
      const host = root.querySelector(`[data-secprog="${sec}"]`);
      if (host) {
        host.querySelector(".bar span").style.width = (secFields.length ? (secFilled / secFields.length) * 100 : 0) + "%";
        host.querySelector("[data-secprog-text]").textContent = secFilled + "/" + secFields.length;
      }
    });

    // overall progress + gate
    root.querySelectorAll("[data-prog-bar]").forEach((el) => (el.style.width = (filled.length / dynFields.length) * 100 + "%"));
    root.querySelectorAll("[data-prog-text]").forEach((el) => (el.textContent = filled.length + "/" + dynFields.length + " fields"));
    document.getElementById("completeMeta").textContent = filled.length + " of " + dynFields.length + " required fields complete";

    const remaining = dynFields.length - filled.length;
    root.querySelectorAll("[data-gen]").forEach((b) => (b.disabled = !complete));
    root.querySelectorAll("[data-why]").forEach((el) => {
      el.className = "why" + (complete ? " ok" : "");
      el.innerHTML = complete
        ? AW.icon("check", 12) + " All required fields complete — ready to generate"
        : AW.icon("warn", 12) + ` ${remaining} required field${remaining === 1 ? "" : "s"} remaining`;
    });
  }

  /* ---------- generate ---------- */
  function generate() {
    const missing = dynFields.filter((f) => entries[f.key] === "" || entries[f.key] == null);
    if (missing.length) return; // impossible via UI — server would also reject

    const calc = calcNow();
    const balances = {};
    const liabilities = {};
    Object.keys(entries).forEach((k) => {
      if (k.startsWith("bal:")) balances[k.slice(4)] = entries[k];
      if (k.startsWith("liab:")) liabilities[k.slice(5)] = entries[k];
    });

    const report = T.createReport(client.id, {
      quarter: RQ.label,
      date: RQ.date,
      balances,
      liabilities,
      zillow: client.trust.exists ? entries.zillow : 0,
      privateReserve: entries.reserve,
      financials: { ...fin },
      calc,
    });
    generated = report;
    AW.toast(RQ.label + " report generated.", "ok");
    renderResult();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ---------- result + history ---------- */
  function renderResult() {
    document.getElementById("vbar").style.display = "none";
    const r = generated;
    const c = r.calc;
    const history = T.listReports(client.id);

    const dl = (cls, icon, title, desc, btnLabel, btnClass) => `
      <div class="dlcard ${cls}">
        <span class="ic-wrap">${AW.icon(icon, 19)}</span>
        <div><h4>${title}</h4><p>${desc}</p></div>
        <button class="btn ${btnClass}" data-dl="${title}">${AW.icon(cls === "canva" ? "copy" : "download", 14)} ${btnLabel}</button>
      </div>`;

    root.innerHTML = `
      <div class="result-hero">
        <div class="check-badge">${AW.icon("check", 24)}</div>
        <h2>${r.quarter} report generated</h2>
        <p>${esc(name)} · saved ${AW.dates.pretty(r.date)} · entries and calculations persisted to history.</p>
        <div class="summary-row">
          <div><div class="k">Grand Net Worth</div><div class="v">${AW.fmt.money(c.grandNetWorth)}</div></div>
          <div><div class="k">Monthly Excess</div><div class="v">${AW.fmt.money(c.excess, { sign: true })}</div></div>
          <div><div class="k">Reserve vs Target</div><div class="v">${AW.fmt.money(c.privateReserveBalance)} / ${AW.fmt.money(c.privateReserveTarget)}</div></div>
          <div><div class="k">Liabilities</div><div class="v">${AW.fmt.money(c.liabilitiesTotal)}</div></div>
        </div>
      </div>

      <div class="dl-grid">
        ${dl("sacs", "file", "SACS PDF", "Asset & cash-flow statement, formatted for client delivery.", "Download SACS PDF", "btn-primary")}
        ${dl("tcc", "file", "TCC PDF", "Reserve & liabilities companion report.", "Download TCC PDF", "btn-ghost")}
        ${dl("canva", "copy", "Canva export", "Push this quarter's numbers into the Canva template.", "Export to Canva", "btn-ghost")}
      </div>

      <section class="section">
        <div class="section-head">
          ${AW.icon("history", 16)}
          <h3>Report history</h3>
          <span class="hint">${history.length} report${history.length === 1 ? "" : "s"} on file</span>
          <div class="spacer"></div>
          <a class="btn btn-ghost btn-sm" href="index.html">${AW.icon("arrowL", 13)} All clients</a>
        </div>
        <table class="table">
          <thead><tr><th>Quarter</th><th>Generated</th><th class="num">Grand Net Worth</th><th class="num">Reserve</th><th style="text-align:right">Downloads</th></tr></thead>
          <tbody>
            ${history.map((h) => `
              <tr>
                <td class="hist-q">${h.quarter}${h.id === r.id ? ' <span class="tag tag-green" style="margin-left:6px">New</span>' : ""}</td>
                <td class="tnum">${AW.dates.pretty(h.date)}</td>
                <td class="num mono">${h.calc ? AW.fmt.money(h.calc.grandNetWorth) : "—"}</td>
                <td class="num mono">${AW.fmt.money(h.privateReserve)}</td>
                <td>
                  <div class="row gap-sm" style="justify-content:flex-end">
                    <button class="btn btn-ghost btn-xs" data-dl="SACS ${h.quarter}">${AW.icon("download", 12)} SACS</button>
                    <button class="btn btn-ghost btn-xs" data-dl="TCC ${h.quarter}">${AW.icon("download", 12)} TCC</button>
                  </div>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </section>`;

    // mock downloads (real app: GET /api/reports/{id}/pdf?type=sacs|tcc)
    root.querySelectorAll("[data-dl]").forEach((b) =>
      b.addEventListener("click", () => AW.toast("Preparing " + b.dataset.dl + "…")));
  }

  /* ---------- layout switcher ---------- */
  const seg = document.getElementById("layoutSeg");
  [...seg.children].forEach((b) => b.classList.toggle("on", b.dataset.l === layout));
  seg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    layout = b.dataset.l;
    localStorage.setItem("aw_layout", layout);
    [...seg.children].forEach((x) => x.classList.toggle("on", x === b));
    renderEntry();
  });

  /* ---------- init ---------- */
  renderEntry();
})();
