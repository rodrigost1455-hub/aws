/* ============================================================
   client-form.js — Client Profile create/edit behavior
   Account/liability builders, spouse structure, validation,
   live baselines, persistence via AW.store.
   ============================================================ */
(async function () {
  document.getElementById("chrome").innerHTML = AW.topbar("clients");
  document.getElementById("trustIcon").innerHTML = AW.icon("home");

  const T = AW.store;
  const id = AW.param("id");
  const existing = id ? await T.getClient(id) : null;

  // ---- working model ----
  const model = existing
    ? clone(existing)
    : {
        id: null,
        married: false,
        client1: { firstName: "", lastName: "", dob: "", ssn: "" },
        client2: null,
        retirement: { 1: [], 2: [] },
        nonRetirement: [],
        trust: { exists: false, address: "" },
        liabilities: [],
        financials: { inflow: "", outflow: "", deductibles: "" },
        lastReportDate: null,
        reports: [],
      };

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function uid() { return "a" + Math.random().toString(36).slice(2, 9); }

  // ---- header / labels ----
  if (existing) {
    document.getElementById("title").textContent = AW.who.displayName(existing);
    document.getElementById("crumbName").textContent = AW.who.displayName(existing);
    document.getElementById("eyebrow").textContent = "Edit household";
    document.title = AW.who.displayName(existing) + " · AW Portal";
  }
  document.querySelector('[data-add="ret1"]').innerHTML = AW.icon("plus", 13) + "Add";
  document.querySelector('[data-add="ret2"]').innerHTML = AW.icon("plus", 13) + "Add";
  document.querySelector('[data-add="nonret"]').innerHTML = AW.icon("plus", 13) + "Add account";
  document.querySelector('[data-add="liab"]').innerHTML = AW.icon("plus", 13) + "Add liability";
  document.getElementById("saveGen").innerHTML = AW.icon("chart", 15) + "Save &amp; Generate report";

  // ===========================================================
  //  Household columns (Client 1 / Client 2)
  // ===========================================================
  function personFields(n, person) {
    const age = AW.dates.age(person.dob);
    return `
      <div class="spouse-col" data-person="${n}">
        <div class="col-head">
          <span class="badge">${n}</span>
          <b>Client ${n}</b>
          <span class="age" data-age>${age != null ? "Age " + age : ""}</span>
        </div>
        <div class="grid g2" style="gap:12px">
          <div class="field" data-f="first">
            <label>First name <span class="req">*</span></label>
            <input class="input" data-k="firstName" value="${esc(person.firstName)}" placeholder="First" />
            <div class="err-msg">Required.</div>
          </div>
          <div class="field" data-f="last">
            <label>Last name <span class="req">*</span></label>
            <input class="input" data-k="lastName" value="${esc(person.lastName)}" placeholder="Last" />
            <div class="err-msg">Required.</div>
          </div>
          <div class="field" data-f="dob">
            <label>Date of birth <span class="req">*</span></label>
            <input class="input" type="date" data-k="dob" value="${esc(person.dob)}" max="2010-01-01" />
            <div class="err-msg">Required.</div>
          </div>
          <div class="field" data-f="ssn">
            <label>SSN — last 4 <span class="req">*</span></label>
            <input class="input mono" data-k="ssn" value="${esc(person.ssn)}" inputmode="numeric" maxlength="4" placeholder="0000" />
            <div class="err-msg">4 digits.</div>
          </div>
        </div>
      </div>`;
  }

  function renderClientCols() {
    const cols = document.getElementById("clientCols");
    let html = personFields(1, model.client1);
    if (model.married) {
      if (!model.client2) model.client2 = { firstName: "", lastName: "", dob: "", ssn: "" };
      html += personFields(2, model.client2);
      cols.classList.remove("g2"); cols.classList.add("g2");
    } else {
      cols.className = "grid g2";
    }
    cols.innerHTML = html;

    // wire each person's inputs
    cols.querySelectorAll("[data-person]").forEach((col) => {
      const n = col.dataset.person;
      const person = n === "1" ? model.client1 : model.client2;
      col.querySelectorAll("[data-k]").forEach((inp) => {
        inp.addEventListener("input", () => {
          let v = inp.value;
          if (inp.dataset.k === "ssn") v = v.replace(/\D/g, "").slice(0, 4);
          inp.value = v;
          person[inp.dataset.k] = v;
          if (inp.dataset.k === "dob") {
            const a = AW.dates.age(v);
            col.querySelector("[data-age]").textContent = a != null ? "Age " + a : "";
          }
          if (inp.dataset.k === "firstName") {
            document.getElementById(n === "1" ? "ret1Label" : "ret2Label").textContent =
              (v || "Client " + n) + " retirement";
          }
          clearErr(inp.closest(".field"));
        });
      });
    });
    // sync ret labels
    document.getElementById("ret1Label").textContent = (model.client1.firstName || "Client 1") + " retirement";
    if (model.client2)
      document.getElementById("ret2Label").textContent = (model.client2.firstName || "Client 2") + " retirement";
    document.getElementById("ret2Wrap").style.display = model.married ? "" : "none";
  }

  // married toggle
  const marriedEl = document.getElementById("married");
  marriedEl.checked = model.married;
  marriedEl.addEventListener("change", () => {
    model.married = marriedEl.checked;
    if (!model.married) { model.client2 = null; model.retirement[2] = []; }
    renderClientCols();
    renderBuilder("ret2", model.retirement[2], retRow);
    updateBaselines();
  });

  // ===========================================================
  //  Account / liability builders
  // ===========================================================
  function selectHtml(opts, val) {
    return `<select class="select" data-k="type">${opts
      .map((o) => `<option ${o === val ? "selected" : ""}>${o}</option>`)
      .join("")}</select>`;
  }

  function retRow(a, i) {
    return `<div class="builder-row ret" data-row="${a.id}">
      <div class="idx">${i + 1}</div>
      <div class="field field-mini"><label>Account type</label>${selectHtml(T.RETIREMENT_TYPES, a.type)}</div>
      <div class="field field-mini"><label>Acct # — last 4</label><input class="input mono" data-k="last4" value="${esc(a.last4)}" inputmode="numeric" maxlength="4" placeholder="0000" /></div>
      <button type="button" class="del" data-del>${AW.icon("trash", 15)}</button>
    </div>`;
  }
  function nonretRow(a, i) {
    return `<div class="builder-row nonret" data-row="${a.id}">
      <div class="idx">${i + 1}</div>
      <div class="field field-mini"><label>Institution / nickname</label><input class="input" data-k="name" value="${esc(a.name || "")}" placeholder="e.g. Schwab" /></div>
      <div class="field field-mini"><label>Account type</label>${selectHtml(T.NONRET_TYPES, a.type)}</div>
      <div class="field field-mini"><label>Acct # — last 4</label><input class="input mono" data-k="last4" value="${esc(a.last4)}" inputmode="numeric" maxlength="4" placeholder="0000" /></div>
      <button type="button" class="del" data-del>${AW.icon("trash", 15)}</button>
    </div>`;
  }
  function liabRow(l, i) {
    return `<div class="builder-row liab" data-row="${l.id}">
      <div class="idx">${i + 1}</div>
      <div class="field field-mini"><label>Liability type</label>${selectHtml(T.LIABILITY_TYPES, l.type)}</div>
      <div class="field field-mini"><label>Interest rate</label><div class="input-affix affix-pct"><input class="input mono" data-k="rate" value="${l.rate != null ? l.rate : ""}" inputmode="decimal" placeholder="0.00" /><span class="affix">%</span></div></div>
      <button type="button" class="del" data-del>${AW.icon("trash", 15)}</button>
    </div>`;
  }

  const builders = {
    ret1: { list: () => model.retirement[1], row: retRow, max: 6, empty: "No retirement accounts yet." },
    ret2: { list: () => model.retirement[2], row: retRow, max: 6, empty: "No retirement accounts yet." },
    nonret: { list: () => model.nonRetirement, row: nonretRow, max: 6, empty: "No non-retirement accounts yet — add Brokerage or Joint." },
    liab: { list: () => model.liabilities, row: liabRow, max: 3, empty: "No liabilities. (Optional — 0 to 3.)" },
  };

  function renderBuilder(key) {
    const cfg = builders[key];
    const list = cfg.list();
    const host = document.getElementById(key);
    if (!host) return;
    if (!list.length) {
      host.innerHTML = `<div class="builder-empty">${cfg.empty}</div>`;
    } else {
      host.innerHTML = list.map((item, i) => cfg.row(item, i)).join("");
    }
    // wire rows
    host.querySelectorAll("[data-row]").forEach((rowEl) => {
      const item = list.find((x) => x.id === rowEl.dataset.row);
      rowEl.querySelectorAll("[data-k]").forEach((inp) => {
        inp.addEventListener("input", () => {
          let v = inp.value;
          if (inp.dataset.k === "last4") {
            v = v.replace(/\D/g, "").slice(0, 4); inp.value = v;
            rowEl.style.borderColor = ""; rowEl.style.background = "";
          }
          if (inp.dataset.k === "rate") { v = v.replace(/[^0-9.]/g, ""); inp.value = v; item.rate = v === "" ? null : Number(v); return; }
          item[inp.dataset.k] = v;
        });
      });
      rowEl.querySelector("[data-del]").addEventListener("click", () => {
        const idx = list.findIndex((x) => x.id === item.id);
        if (idx >= 0) list.splice(idx, 1);
        renderBuilder(key);
        updateBaselines();
      });
    });
    // toggle add-button disabled at max
    const addBtn = document.querySelector(`[data-add="${key}"]`);
    if (addBtn) addBtn.toggleAttribute("disabled", list.length >= cfg.max);
  }

  document.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.add;
      const cfg = builders[key];
      const list = cfg.list();
      if (list.length >= cfg.max) return;
      if (key === "ret1") list.push({ id: uid(), spouse: 1, type: T.RETIREMENT_TYPES[0], last4: "", name: null });
      else if (key === "ret2") list.push({ id: uid(), spouse: 2, type: T.RETIREMENT_TYPES[0], last4: "", name: null });
      else if (key === "nonret") list.push({ id: uid(), type: T.NONRET_TYPES[0], last4: "", name: "" });
      else if (key === "liab") list.push({ id: uid(), type: T.LIABILITY_TYPES[0], rate: null });
      renderBuilder(key);
      updateBaselines();
    });
  });

  // ===========================================================
  //  Trust
  // ===========================================================
  const trustExists = document.getElementById("trustExists");
  const trustAddrField = document.getElementById("trustAddrField");
  const trustAddress = document.getElementById("trustAddress");
  trustExists.checked = model.trust.exists;
  trustAddress.value = model.trust.address || "";
  trustAddrField.style.display = model.trust.exists ? "" : "none";
  trustExists.addEventListener("change", () => {
    model.trust.exists = trustExists.checked;
    trustAddrField.style.display = trustExists.checked ? "" : "none";
  });
  trustAddress.addEventListener("input", () => {
    model.trust.address = trustAddress.value;
    clearErr(trustAddrField);
  });

  // ===========================================================
  //  Financial baselines
  // ===========================================================
  const inflowEl = document.getElementById("inflow");
  const outflowEl = document.getElementById("outflow");
  const dedEl = document.getElementById("deductibles");
  inflowEl.value = model.financials.inflow ? AW.fmt.num(model.financials.inflow) : "";
  outflowEl.value = model.financials.outflow ? AW.fmt.num(model.financials.outflow) : "";
  dedEl.value = model.financials.deductibles ? AW.fmt.num(model.financials.deductibles) : "";

  AW.bindCurrency(inflowEl, (v) => { model.financials.inflow = v; updateBaselines(); clearErr(document.getElementById("f-inflow")); });
  AW.bindCurrency(outflowEl, (v) => { model.financials.outflow = v; updateBaselines(); clearErr(document.getElementById("f-outflow")); });
  AW.bindCurrency(dedEl, (v) => { model.financials.deductibles = v; updateBaselines(); clearErr(document.getElementById("f-deductibles")); });

  function updateBaselines() {
    const inf = AW.fmt.parse(model.financials.inflow);
    const out = AW.fmt.parse(model.financials.outflow);
    const ded = AW.fmt.parse(model.financials.deductibles);
    document.getElementById("prevExcess").textContent = AW.fmt.money(inf - out, { sign: true });
    document.getElementById("prevReserve").textContent = AW.fmt.money(6 * out + ded);
    const accts =
      model.retirement[1].length + model.retirement[2].length + model.nonRetirement.length;
    document.getElementById("prevAccts").textContent = accts;
    document.getElementById("saveSummary").textContent =
      accts + " account" + (accts === 1 ? "" : "s") +
      (model.liabilities.length ? " · " + model.liabilities.length + " liability" + (model.liabilities.length === 1 ? "" : "s") : "");
  }

  // ===========================================================
  //  Validation + save
  // ===========================================================
  function esc(s) { return String(s == null ? "" : s).replace(/"/g, "&quot;").replace(/</g, "&lt;"); }
  function clearErr(field) { if (field) field.classList.remove("field-err"); }
  function setErr(field) { if (field) field.classList.add("field-err"); return field; }

  function validate() {
    let ok = true;
    let firstBad = null;

    // people
    document.querySelectorAll("[data-person]").forEach((col) => {
      const n = col.dataset.person;
      const person = n === "1" ? model.client1 : model.client2;
      [["first", "firstName"], ["last", "lastName"], ["dob", "dob"]].forEach(([f, k]) => {
        const field = col.querySelector(`[data-f="${f}"]`);
        if (!String(person[k] || "").trim()) { setErr(field); ok = false; firstBad = firstBad || field; }
        else clearErr(field);
      });
      const ssnField = col.querySelector('[data-f="ssn"]');
      if (!/^\d{4}$/.test(person.ssn || "")) { setErr(ssnField); ok = false; firstBad = firstBad || ssnField; }
      else clearErr(ssnField);
    });

    // at least one retirement account on client 1
    if (model.retirement[1].length === 0) {
      AW.toast("Add at least one retirement account for Client 1.");
      ok = false;
    }

    // every account row needs a 4-digit last-4
    document.querySelectorAll(".builder-row").forEach((rowEl) => {
      const inp = rowEl.querySelector('[data-k="last4"]');
      if (!inp) return;
      const bad = !/^\d{4}$/.test(inp.value);
      rowEl.style.borderColor = bad ? "#f0a5a5" : "";
      rowEl.style.background = bad ? "#fffafa" : "";
      if (bad) { ok = false; firstBad = firstBad || rowEl; }
    });

    // trust address if exists
    if (model.trust.exists && !String(model.trust.address || "").trim()) {
      setErr(trustAddrField); ok = false; firstBad = firstBad || trustAddrField;
    }

    // financials required
    [["f-inflow", "inflow"], ["f-outflow", "outflow"], ["f-deductibles", "deductibles"]].forEach(([fid, k]) => {
      const field = document.getElementById(fid);
      if (!model.financials[k] && model.financials[k] !== 0) { setErr(field); ok = false; firstBad = firstBad || field; }
      else clearErr(field);
    });

    if (firstBad) firstBad.querySelector("input,textarea,select")?.focus();
    return ok;
  }

  function persist() {
    // normalize numeric financials
    model.financials.inflow = AW.fmt.parse(model.financials.inflow);
    model.financials.outflow = AW.fmt.parse(model.financials.outflow);
    model.financials.deductibles = AW.fmt.parse(model.financials.deductibles);
    // Server assigns ids if missing — strip the temporary client-side id.
    const payload = JSON.parse(JSON.stringify(model));
    return T.saveClient(payload);
  }

  document.getElementById("saveOnly").addEventListener("click", async () => {
    if (!validate()) { AW.toast("Some required fields need attention."); return; }
    try {
      await persist();
    } catch (e) {
      AW.toast("Save failed: " + (e.message || "network error"));
      return;
    }
    AW.toast("Profile saved.", "ok");
    setTimeout(() => (location.href = "index.html"), 700);
  });

  document.getElementById("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validate()) { AW.toast("Some required fields need attention."); return; }
    let saved;
    try {
      saved = await persist();
    } catch (err) {
      AW.toast("Save failed: " + (err.message || "network error"));
      return;
    }
    AW.toast("Profile saved.", "ok");
    setTimeout(() => (location.href = "report.html?id=" + saved.id), 600);
  });

  // ---- initial paint ----
  renderClientCols();
  ["ret1", "ret2", "nonret", "liab"].forEach(renderBuilder);
  updateBaselines();
})();
