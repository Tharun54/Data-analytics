/* CSE Plus single-page app. No build step: plain JS + Chart.js. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const app = $("#app");
const charts = new Set();
let me = null;

// ---------- utilities ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (a >= 1e4) return (n / 1e3).toFixed(1) + "K";
  return Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
};
const ago = (iso) => {
  const s = (Date.now() - new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z")) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
};
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 3200);
}
const token = {
  get: () => { try { return localStorage.getItem("cse_token"); } catch { return token._mem; } },
  set: (v) => { token._mem = v; try { v ? localStorage.setItem("cse_token", v) : localStorage.removeItem("cse_token"); } catch {} },
};

async function api(path, opts = {}) {
  const headers = opts.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const t = token.get();
  if (t) headers.Authorization = "Bearer " + t;
  const res = await fetch(path, {
    ...opts, headers: { ...headers, ...(opts.headers || {}) },
    body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
  });
  if (res.status === 401 && !path.startsWith("/api/auth")) { token.set(null); location.hash = "#/login"; throw new Error("Session expired"); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(Array.isArray(d) ? d.map((e) => e.msg).join("; ") : d || res.statusText);
  }
  return data;
}

// ---------- theme ----------
function applyTheme(t) {
  if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  try { t ? localStorage.setItem("cse_theme", t) : localStorage.removeItem("cse_theme"); } catch {}
}
try { const t = localStorage.getItem("cse_theme"); if (t) applyTheme(t); } catch {}
$("#theme-toggle").onclick = () => {
  const dark = getComputedStyle(document.documentElement).colorScheme === "dark";
  applyTheme(dark ? "light" : "dark");
  route(); // re-render charts with the new palette
};
$("#logout").onclick = () => { token.set(null); me = null; location.hash = "#/login"; };

// ---------- chart rendering ----------
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const seriesColor = (i) => cssVar(`--s${(i % 8) + 1}`);

function destroyCharts() { charts.forEach((c) => c.destroy()); charts.clear(); }

function renderChart(canvas, spec) {
  const pie = spec.type === "pie" || spec.type === "doughnut";
  const surface = cssVar("--surface");
  const datasets = spec.series.map((s, i) => {
    const color = seriesColor(i);
    if (pie) {
      return { label: s.name, data: s.data, backgroundColor: s.data.map((_, j) => seriesColor(j)),
        borderColor: surface, borderWidth: 2, borderRadius: 4 };
    }
    const area = spec.type === "area";
    return {
      label: s.name, data: s.data, borderColor: color, backgroundColor: area ? color + "33" : color,
      fill: area ? "origin" : false, borderWidth: 2, tension: 0.25,
      pointRadius: spec.labels.length > 24 ? 0 : 3, pointHoverRadius: 5, pointBackgroundColor: color,
      pointBorderColor: surface, pointBorderWidth: 2,
      borderRadius: spec.type === "bar" ? { topLeft: 4, topRight: 4 } : 0, borderSkipped: "start",
      maxBarThickness: 36, categoryPercentage: 0.8, barPercentage: 0.9,
    };
  });
  const ink2 = cssVar("--ink-2"), muted = cssVar("--muted"), grid = cssVar("--grid"), axis = cssVar("--axis");
  const chart = new Chart(canvas, {
    type: spec.type === "area" ? "line" : spec.type,
    data: { labels: spec.labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      interaction: pie ? { mode: "nearest", intersect: true } : { mode: "index", intersect: false },
      cutout: spec.type === "doughnut" ? "62%" : undefined,
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: cssVar("--ink"), titleColor: cssVar("--page"), bodyColor: cssVar("--page"),
          padding: 10, cornerRadius: 8, boxPadding: 4, usePointStyle: true,
          callbacks: { label: (c) => ` ${c.dataset.label === c.label ? "" : (pie ? c.label : c.dataset.label) + ": "}${fmt(c.parsed.y ?? c.parsed)}` } },
      },
      scales: pie ? {} : {
        x: { grid: { display: false }, border: { color: axis }, ticks: { color: muted, maxRotation: 0, autoSkipPadding: 12, font: { size: 11 } } },
        y: { grid: { color: grid }, border: { display: false }, beginAtZero: spec.type === "bar", ticks: { color: muted, callback: fmt, font: { size: 11 } } },
      },
      color: ink2,
    },
  });
  charts.add(chart);
}

function legendHtml(spec) {
  const pie = spec.type === "pie" || spec.type === "doughnut";
  const items = pie ? spec.labels : spec.series.map((s) => s.name);
  if (items.length < 2) return "";
  return `<div class="legend">${items.map((n, i) => `<span><i style="background:${seriesColor(i)}"></i>${esc(n)}</span>`).join("")}</div>`;
}

function tableHtml(spec) {
  return `<div class="table-wrap"><table class="data"><thead><tr><th></th>${spec.series.map((s) => `<th class="num">${esc(s.name)}</th>`).join("")}</tr></thead>
    <tbody>${spec.labels.map((l, i) => `<tr><td>${esc(l)}</td>${spec.series.map((s) => `<td class="num">${fmt(s.data[i])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function chartCard(spec, extra = "") {
  const id = "c" + Math.random().toString(36).slice(2);
  setTimeout(() => {
    const el = document.getElementById(id);
    if (!el) return;
    renderChart(el.querySelector("canvas"), spec);
    el.querySelector("[data-toggle]").onclick = (e) => {
      const showTable = e.target.textContent === "Table";
      el.querySelector(".chart-box").hidden = showTable;
      el.querySelector(".tbl").hidden = !showTable;
      e.target.textContent = showTable ? "Chart" : "Table";
    };
  });
  return `<div class="card chart-card widget" id="${id}">${extra}
    <div class="chart-head"><h3>${esc(spec.title)}</h3><button class="btn ghost sm" data-toggle>Table</button></div>
    ${legendHtml(spec)}
    <div class="chart-box"><canvas role="img" aria-label="${esc(spec.title)}"></canvas></div>
    <div class="tbl" hidden>${tableHtml(spec)}</div>
    ${spec.insight ? `<p class="chart-insight">${esc(spec.insight)}</p>` : ""}</div>`;
}

function kpiCard(k, extra = "") {
  const d = k.change_pct;
  const delta = d === null || d === undefined ? "" :
    `<div class="delta ${d >= 0 ? "up" : "down"}">${d >= 0 ? "▲" : "▼"} ${Math.abs(d).toFixed(1)}%</div>`;
  return `<div class="card kpi widget">${extra}<div class="label">${esc(k.label)}</div>
    <div class="value">${fmt(k.value)}<small>${esc(k.unit)}</small></div>${delta}<div class="note">${esc(k.note)}</div></div>`;
}

const summaryCard = (s, extra = "") => `<div class="card widget">${extra}
  <div class="row"><h2 style="flex:1">${esc(s.title)}</h2><span class="status">confidence: ${esc(s.confidence)}</span></div>
  <p class="ink2">${esc(s.summary)}</p>
  ${s.sources?.length ? `<details class="sources"><summary class="muted">${s.sources.length} sources</summary><ol>${s.sources.map((x) =>
    `<li><a href="${esc(/^https?:\/\//.test(x.url) ? x.url : "#")}" target="_blank" rel="noopener noreferrer">${esc(x.title)}</a></li>`).join("")}</ol></details>` : ""}</div>`;

const insightsCard = (list, extra = "") => `<div class="card widget">${extra}<h2>Key insights</h2>${list.map((i) =>
  `<div class="insight"><strong>${esc(i.headline)}</strong><span class="impact">${esc(i.impact)}</span><div class="ink2">${esc(i.detail)}</div></div>`).join("")}</div>`;

const swotCard = (s, extra = "") => `<div class="card widget">${extra}<h2>SWOT</h2><div class="swot">${["strengths", "weaknesses", "opportunities", "threats"].map((k) =>
  `<div><h3 style="text-transform:capitalize">${k}</h3><ul>${(s[k] || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`).join("")}</div></div>`;

const recsCard = (r, extra = "") => `<div class="card widget">${extra}<h2>Recommendations</h2><ol class="recs">${r.map((x) => `<li>${esc(x)}</li>`).join("")}</ol></div>`;

function reportHtml(r) {
  return `${summaryCard(r)}
    <div class="grid kpis section">${r.kpis.map((k) => kpiCard(k)).join("")}</div>
    <div class="grid charts section">${r.charts.map((c) => chartCard(c)).join("")}</div>
    <div class="grid two section">
      ${r.insights.length ? insightsCard(r.insights) : ""}
      ${r.recommendations.length ? recsCard(r.recommendations) : ""}
    </div>
    ${Object.values(r.swot).some((v) => v.length) ? `<div class="section">${swotCard(r.swot)}</div>` : ""}`;
}

// ---------- views ----------
function authView(mode) {
  $("#topbar").hidden = true;
  const signup = mode === "signup";
  app.innerHTML = `<div class="auth card">
    <div class="brand"><span class="logo">C+</span> CSE Plus</div>
    <h1>${signup ? "Create your workspace" : "Welcome back"}</h1>
    <p class="ink2">${signup ? "Analysis on any topic, delivered as live dashboards." : "Log in to your analytics workspace."}</p>
    <form id="f">
      ${signup ? `<label>Your name</label><input name="name" required autocomplete="name">
      <label>Company</label><input name="company" required autocomplete="organization">` : ""}
      <label>Email</label><input name="email" type="email" required autocomplete="email">
      <label>Password</label><input name="password" type="password" required minlength="${signup ? 8 : 1}" autocomplete="${signup ? "new-password" : "current-password"}">
      <div class="row" style="margin-top:16px"><button class="btn" type="submit">${signup ? "Create account" : "Log in"}</button>
      <span class="spacer"></span><a href="#/${signup ? "login" : "signup"}">${signup ? "I have an account" : "Create an account"}</a></div>
    </form></div>`;
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target));
    try {
      const r = await api(`/api/auth/${signup ? "signup" : "login"}`, { method: "POST", body });
      token.set(r.access_token);
      me = null;
      location.hash = "#/";
    } catch (err) { toast(err.message); }
  };
}

const EXAMPLES = ["Electric vehicle market in India", "Generative AI adoption in healthcare", "Global coffee prices 2026",
  "Remote work trends", "Quick-commerce in Southeast Asia", "Renewable energy investment in Europe"];

async function homeView() {
  const list = await api("/api/analyses");
  app.innerHTML = `<div class="card hero">
      <h1>What do you want analysed?</h1>
      <p class="ink2">Type any topic — a market, company, technology, trend or policy. CSE Plus researches it and builds a dashboard.</p>
      <form id="ask" class="ask"><input name="topic" placeholder="e.g. Electric vehicle market in India" required minlength="3" maxlength="500" autofocus>
        <button class="btn" type="submit">Analyze</button></form>
      <div class="chips">${EXAMPLES.map((x) => `<button type="button" class="chip">${esc(x)}</button>`).join("")}</div>
    </div>
    <div class="card section"><div class="row"><h2 style="flex:1">Recent analyses</h2>
      <span class="muted">${me.usage.analysis} / ${me.plan.analyses_per_month} this month</span></div>
      ${list.length ? `<ul class="list">${list.map((a) => `<li>
        <div style="flex:1;min-width:0"><a class="title" href="#/analyses/${a.id}">${esc(a.title || a.topic)}</a>
        <div class="muted" style="font-size:13px">${esc(a.source === "dataset" ? "Dataset" : "Topic")} · ${a.engine} · ${ago(a.created_at)}</div></div>
        <span class="status ${a.status}">${a.status}</span></li>`).join("")}</ul>` : `<div class="empty">No analyses yet — try one of the examples above.</div>`}
    </div>`;
  app.querySelectorAll(".chip").forEach((c) => (c.onclick = () => { $("#ask [name=topic]").value = c.textContent; }));
  $("#ask").onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    try {
      const a = await api("/api/analyses", { method: "POST", body: { topic: e.target.topic.value } });
      location.hash = `#/analyses/${a.id}`;
    } catch (err) { toast(err.message); btn.disabled = false; }
  };
  if (list.some((a) => a.status === "pending" || a.status === "running")) poll(homeView);
}

function poll(fn) {
  const h = location.hash;
  setTimeout(() => { if (location.hash === h) fn().catch((e) => toast(e.message)); }, 2500);
}

async function analysisView(id) {
  const a = await api(`/api/analyses/${id}`);
  if (a.status === "pending" || a.status === "running") {
    app.innerHTML = `<div class="card empty"><h2><span class="spinner"></span> Analysing “${esc(a.topic)}”</h2>
      <p>${a.engine === "ai" ? "Researching sources, extracting figures and building charts. This usually takes 1–3 minutes." : "Generating demo report…"}</p></div>`;
    return poll(() => analysisView(id));
  }
  if (a.status === "failed") {
    app.innerHTML = `<div class="card empty"><h2>Analysis failed</h2><p>${esc(a.error)}</p><a class="btn" href="#/">Try again</a></div>`;
    return;
  }
  app.innerHTML = `<div class="page-head"><div><a href="#/" class="muted">← Analyses</a></div>
      <button class="btn ghost" id="del">Delete</button><button class="btn" id="mk">Create dashboard</button></div>
    ${reportHtml(a.result)}`;
  $("#mk").onclick = async () => {
    try { const d = await api(`/api/analyses/${id}/dashboard`, { method: "POST" }); location.hash = `#/dashboards/${d.id}`; }
    catch (err) { toast(err.message); }
  };
  $("#del").onclick = async () => {
    if (!confirm("Delete this analysis? It will also be removed from dashboards.")) return;
    await api(`/api/analyses/${id}`, { method: "DELETE" });
    location.hash = "#/";
  };
}

async function dashboardsView() {
  const list = await api("/api/dashboards");
  const lim = me.plan.dashboards;
  app.innerHTML = `<div class="page-head"><div><h1>Dashboards</h1><p class="ink2">Dedicated, shareable dashboards built from your analyses.</p></div>
    <span class="muted">${list.length}${lim ? " / " + lim : ""} used</span><button class="btn" id="new">New dashboard</button></div>
    ${list.length ? `<div class="grid two">${list.map((d) => `<a class="card" href="#/dashboards/${d.id}" style="color:inherit">
      <h2>${esc(d.name)}</h2><p class="ink2">${esc(d.description)}</p>
      <div class="muted" style="font-size:13px">${d.widgets} widgets · updated ${ago(d.updated_at)}${d.shared ? " · 🔗 shared" : ""}</div></a>`).join("")}</div>`
      : `<div class="card empty">No dashboards yet. Open an analysis and click <strong>Create dashboard</strong>.</div>`}`;
  $("#new").onclick = async () => {
    const name = prompt("Dashboard name");
    if (!name) return;
    try { const d = await api("/api/dashboards", { method: "POST", body: { name } }); location.hash = `#/dashboards/${d.id}`; }
    catch (err) { toast(err.message); }
  };
}

function widgetHtml(w, removable) {
  const x = removable ? `<button class="btn danger sm remove" data-remove>Remove</button>` : "";
  switch (w.kind) {
    case "kpi": return kpiCard(w.data, x);
    case "chart": return chartCard(w.data, x);
    case "summary": return summaryCard(w.data, x);
    case "insights": return insightsCard(w.data, x);
    case "swot": return swotCard(w.data, x);
    case "recommendations": return recsCard(w.data, x);
    default: return "";
  }
}

function layoutWidgets(widgets, removable) {
  // Group consecutive widgets of the same layout class so KPIs tile and charts flow in a grid.
  const cls = (k) => (k === "kpi" ? "kpis" : k === "chart" ? "charts" : "two");
  let html = "", group = null, buf = [];
  const flush = () => { if (buf.length) html += `<div class="grid ${group} section">${buf.join("")}</div>`; buf = []; };
  widgets.forEach((w, i) => {
    const g = w.kind === "summary" ? "one" : cls(w.kind);
    if (g !== group) { flush(); group = g; }
    buf.push(`<div data-i="${i}" style="display:contents">${widgetHtml(w, removable)}</div>`);
  });
  flush();
  return html.replaceAll('class="grid one section"', 'class="section"');
}

async function dashboardView(id) {
  const d = await api(`/api/dashboards/${id}`);
  const shareUrl = d.share_token ? `${location.origin}/share/${d.share_token}` : "";
  app.innerHTML = `<div class="page-head"><div><a href="#/dashboards" class="muted">← Dashboards</a><h1>${esc(d.name)}</h1>
      <p class="ink2">${esc(d.description)}</p></div>
      <button class="btn ghost" id="edit">Edit</button>
      <button class="btn ghost" id="share">${d.shared ? "Sharing on" : "Share"}</button>
      <button class="btn danger" id="del">Delete</button></div>
    ${d.shared ? `<div class="card" style="margin-bottom:16px"><div class="row"><span style="flex:1;min-width:0;word-break:break-all">Public link: <a href="${esc(shareUrl)}" target="_blank" rel="noopener">${esc(shareUrl)}</a></span>
      <button class="btn ghost sm" id="copy">Copy</button><button class="btn danger sm" id="unshare">Stop sharing</button></div></div>` : ""}
    <div id="widgets">${d.widgets.length ? layoutWidgets(d.widgets, true) : `<div class="card empty">This dashboard is empty. Open an analysis and click “Create dashboard”, or add widgets via the API.</div>`}</div>`;
  $("#edit").onclick = (e) => { const on = $("#widgets").classList.toggle("editing"); e.target.textContent = on ? "Done" : "Edit"; };
  $("#widgets").onclick = async (e) => {
    if (!e.target.matches("[data-remove]")) return;
    const i = +e.target.closest("[data-i]").dataset.i;
    const widgets = d.widgets.filter((_, j) => j !== i).map(({ analysis_id, kind, index }) => ({ analysis_id, kind, index }));
    await api(`/api/dashboards/${id}`, { method: "PATCH", body: { widgets } });
    await dashboardView(id);
    $("#widgets").classList.add("editing"); $("#edit").textContent = "Done";
  };
  $("#share").onclick = async () => {
    try { await api(`/api/dashboards/${id}/share`, { method: "POST" }); dashboardView(id); } catch (err) { toast(err.message); }
  };
  if ($("#unshare")) $("#unshare").onclick = async () => { await api(`/api/dashboards/${id}/share`, { method: "DELETE" }); dashboardView(id); };
  if ($("#copy")) $("#copy").onclick = () => navigator.clipboard.writeText(shareUrl).then(() => toast("Link copied"));
  $("#del").onclick = async () => {
    if (!confirm("Delete this dashboard?")) return;
    await api(`/api/dashboards/${id}`, { method: "DELETE" });
    location.hash = "#/dashboards";
  };
}

async function datasetsView() {
  const list = await api("/api/datasets");
  app.innerHTML = `<div class="page-head"><div><h1>Datasets</h1><p class="ink2">Upload a CSV to get an instant profiled dashboard. Add a question to get an AI analysis grounded in your data.</p></div></div>
    <form class="card" id="up">
      <label class="dropzone" id="dz"><input type="file" name="file" accept=".csv,text/csv" hidden required>
        <strong>Drop a CSV here</strong> or click to choose · max 10 MB</label>
      <label>Question about this data (optional)</label>
      <input name="question" maxlength="500" placeholder="e.g. Which regions are driving revenue growth and why?">
      <div class="row" style="margin-top:12px"><span id="fname" class="muted"></span><span class="spacer"></span><button class="btn" type="submit">Upload & analyse</button></div>
    </form>
    <div class="card section"><h2>Your datasets</h2>${list.length ? `<ul class="list">${list.map((d) =>
      `<li><div style="flex:1;min-width:0"><span class="title">${esc(d.name)}</span><div class="muted" style="font-size:13px">${d.rows.toLocaleString()} rows · ${d.columns.length} columns · ${ago(d.created_at)}</div></div></li>`).join("")}</ul>`
      : `<div class="empty">No datasets yet.</div>`}</div>`;
  const dz = $("#dz"), input = dz.querySelector("input");
  const show = () => ($("#fname").textContent = input.files[0]?.name || "");
  input.onchange = show;
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("over"); };
  dz.ondragleave = () => dz.classList.remove("over");
  dz.ondrop = (e) => { e.preventDefault(); dz.classList.remove("over"); input.files = e.dataTransfer.files; show(); };
  $("#up").onsubmit = async (e) => {
    e.preventDefault();
    if (!input.files[0]) return toast("Choose a CSV file first");
    const fd = new FormData(e.target);
    if (!fd.get("question")) fd.delete("question");
    const btn = e.target.querySelector("button[type=submit]");
    btn.disabled = true;
    try {
      const r = await api("/api/datasets", { method: "POST", body: fd });
      location.hash = `#/analyses/${(r.ai_analysis || r.analysis).id}`;
    } catch (err) { toast(err.message); btn.disabled = false; }
  };
}

async function billingView() {
  const plans = await api("/api/plans");
  const meter = (used, lim) => `<div class="meter"><span style="width:${lim ? Math.min(100, (used / lim) * 100) : 0}%"></span></div>`;
  app.innerHTML = `<div class="page-head"><div><h1>Plan & usage</h1><p class="ink2">${esc(me.org.name)} · ${esc(me.plan.name)} plan</p></div></div>
    <div class="grid two"><div class="card"><h3>Analyses this month</h3><div class="row"><strong>${me.usage.analysis}</strong><span class="muted">of ${me.plan.analyses_per_month}</span></div>${meter(me.usage.analysis, me.plan.analyses_per_month)}
      <h3>Dataset uploads this month</h3><div class="row"><strong>${me.usage.dataset}</strong><span class="muted">of ${me.plan.datasets_per_month}</span></div>${meter(me.usage.dataset, me.plan.datasets_per_month)}</div></div>
    <div class="grid two section">${Object.entries(plans).map(([k, p]) => `<div class="card plan ${k === me.org.plan ? "current" : ""}">
      <h2>${esc(p.name)}</h2><div class="price">$${p.price_usd}<small class="muted" style="font-size:1rem">/mo</small></div>
      <ul><li>${p.analyses_per_month} analyses / month</li><li>${p.datasets_per_month} dataset uploads / month</li>
      <li>${p.dashboards ?? "Unlimited"} dashboards</li><li>${p.web_research ? "Live web research with sources" : "Model knowledge only"}</li>
      <li>${p.sharing ? "Public dashboard links" : "Private dashboards"}</li></ul>
      ${k === me.org.plan ? `<button class="btn ghost" disabled>Current plan</button>` : `<button class="btn" data-plan="${k}">Switch to ${esc(p.name)}</button>`}</div>`).join("")}</div>
    <p class="muted section" style="font-size:13px">Payments: plan switching is instant in this build. Stripe Checkout is wired in at launch (see docs/ROADMAP.md).</p>`;
  app.querySelectorAll("[data-plan]").forEach((b) => (b.onclick = async () => {
    try { await api("/api/billing/plan", { method: "POST", body: { plan: b.dataset.plan } }); me = null; toast("Plan updated"); route(); }
    catch (err) { toast(err.message); }
  }));
}

async function publicView(tokenStr) {
  $("#topbar").hidden = true;
  const d = await api(`/api/public/dashboards/${encodeURIComponent(tokenStr)}`);
  app.innerHTML = `<div class="page-head"><div><div class="brand" style="margin-bottom:12px"><span class="logo">C+</span> CSE Plus</div>
    <h1>${esc(d.name)}</h1><p class="ink2">${esc(d.description)}</p></div></div>${layoutWidgets(d.widgets, false)}
    <p class="muted section" style="text-align:center;font-size:13px">Built with CSE Plus · analysis on any topic</p>`;
}

// ---------- router ----------
async function route() {
  destroyCharts();
  const shared = location.pathname.match(/^\/share\/([\w-]+)/);
  if (shared) return publicView(shared[1]).catch((e) => (app.innerHTML = `<div class="card empty">${esc(e.message)}</div>`));

  const hash = location.hash.replace(/^#/, "") || "/";
  if (hash === "/login" || hash === "/signup") return authView(hash.slice(1));
  if (!token.get()) { location.hash = "#/login"; return; }
  try {
    if (!me) me = await api("/api/me");
    $("#topbar").hidden = false;
    $("#engine-pill").textContent = me.engine === "ai" ? "AI engine" : "Demo engine";
    $("#engine-pill").title = me.engine === "ai" ? "Live AI research" : "No API key configured: synthetic demo data";
    const section = hash.split("/")[1] || "home";
    document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === (section === "analyses" ? "home" : section)));
    let m;
    if ((m = hash.match(/^\/analyses\/(\d+)$/))) await analysisView(m[1]);
    else if ((m = hash.match(/^\/dashboards\/(\d+)$/))) await dashboardView(m[1]);
    else if (hash === "/dashboards") await dashboardsView();
    else if (hash === "/datasets") await datasetsView();
    else if (hash === "/billing") await billingView();
    else { me = await api("/api/me"); await homeView(); }
  } catch (e) {
    app.innerHTML = `<div class="card empty"><h2>Something went wrong</h2><p>${esc(e.message)}</p></div>`;
  }
}
window.addEventListener("hashchange", route);
route();
