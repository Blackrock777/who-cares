/* Clienti che non esistono: front end. Plain JS, no build step. Data: window.DATA (web/data.js), strings: window.I18N. */
(() => {
const D = window.DATA;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const h = (tag, attrs = {}, html = "") => { const e = document.createElement(tag); for (const k in attrs) e.setAttribute(k, attrs[k]); e.innerHTML = html; return e; };
const NS = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs = {}) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const mean = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : NaN;
const rng = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------------- language ---------------- */
const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
let LANG = store.get("lang") || "it";          // the jury is Italian: Italian unless the viewer picked English
const t = (k, v = {}) => { let s = (I18N[LANG] && I18N[LANG][k]) ?? I18N.en[k] ?? k; for (const x in v) s = s.split("{" + x + "}").join(v[x]); return s; };
const loc = () => LANG === "it" ? "it-IT" : "en-GB";
const fmt = (x, n = 2) => x == null || !isFinite(x) ? "–" : Number(x).toLocaleString(loc(), { minimumFractionDigits: n, maximumFractionDigits: n });
const eur = (x, n = 2) => "€" + fmt(x, n);
const pct = x => Math.round(x * 100) + "%";
const dshort = s => new Date(s + "T00:00:00").toLocaleDateString(loc(), { day: "numeric", month: "short" });
const lever = l => t("lever." + l) !== "lever." + l ? t("lever." + l) : (l || "").replace(/_/g, " ");
const fmtName = f => t("fmt." + f) !== "fmt." + f ? t("fmt." + f) : f;
function applyStatic() {
  document.documentElement.lang = LANG;
  $$("[data-i18n]").forEach(e => (e.textContent = t(e.dataset.i18n)));
  $$("[data-i18n-html]").forEach(e => (e.innerHTML = t(e.dataset.i18nHtml)));
  $$("[data-i18n-aria]").forEach(e => e.setAttribute("aria-label", t(e.dataset.i18nAria)));
  $$("#lang button").forEach(b => b.classList.toggle("on", b.dataset.l === LANG));
}

const BRAND = { NDL: "#c4694f", CDF: "#6c8a5f", FGR: "#3f6e8c" };
const AD_COLORS = ["var(--ink)", "#c4694f", "#3f6e8c", "#6c8a5f", "#b5832a", "#8a5a7a"];
const cells = D.priors.cells;
const effCTR = D.priors.cell_effects.ctr.log_mult;

let state = { brand: "NDL", adset: null, kpi: "ctr", labCell: null, hidden: new Set(), studioAud: null, live: null, runs: Object.assign({}, D.studio || {}) };
const brandSets = () => D.adsets.filter(s => s.advertiser === state.brand);
const adsOf = sid => D.ads.filter(a => a.adset === sid && D.forecast[a.id]);
const creative = id => D.creatives.find(c => c.id === id);
const adv = id => D.advertisers.find(a => a.id === id);
const setById = id => D.adsets.find(x => x.id === id);

/* audience label, computed here so both languages read the same numbers */
function audLabel(P) {
  const f = P.share_female.mean, a = P.mean_age.mean, s = P.shift_in_prior_sd;
  const g = f >= 0.65 ? t("g.women") : f <= 0.35 ? t("g.men") : t("g.mixed");
  const lo = Math.floor(Math.max(18, Math.round(a - 9)) / 5) * 5;
  const vs = [];
  if (Math.abs(s.share_female) >= 0.5) vs.push(s.share_female > 0 ? t("vs.morew") : t("vs.morem"));
  if (Math.abs(s.mean_age) >= 0.5) vs.push(s.mean_age > 0 ? t("vs.older") : t("vs.younger"));
  const conf = Math.max(Math.abs(s.share_female), Math.abs(s.mean_age)) >= 1 ? t("conf.data") : vs.length ? t("conf.partly") : t("conf.prior");
  return { headline: `${g}, ${t("around", { a: lo, b: lo + 15 })}`, short: P.p_warm >= 0.7 ? t("fc.retarget") : t("around", { a: lo, b: lo + 15 }), vs: vs.length ? vs : [t("vs.close")], conf };
}
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : s;

/* ---------------- people ---------------- */
function crowd(set, n, seed = 7) {
  const r = rng(seed), P = set.population, w = cells.map(c => P.cells[c].share);
  const z = w.reduce((s, x, i) => s + x * Math.exp(effCTR[cells[i]]), 0);
  const cum = []; w.reduce((s, x, i) => (cum[i] = s + x), 0);
  return Array.from({ length: n }, () => {
    const u = r() * cum[cum.length - 1]; let k = cum.findIndex(x => x >= u); if (k < 0) k = cells.length - 1;
    const [g, band] = cells[k].split("|");
    const lo = band === "55+" ? 55 : +band.split("-")[0], hi = band === "55+" ? 74 : +band.split("-")[1];
    return { g, band, cell: cells[k], age: Math.floor(lo + r() * (hi - lo + 1)), rel: Math.exp(effCTR[cells[k]]) / z };
  });
}
const personColor = p => `color-mix(in srgb, ${p.g === "F" ? css("--women") : css("--men")} ${Math.round(45 + 55 * Math.min(1, Math.max(0, (p.age - 18) / 56)))}%, var(--paper))`;
function runCrowd(container, outEl, people, ctr) {
  const dots = $$("i", container), seed = rng(Date.now() % 1e6); let clicks = 0; const by = {};
  dots.forEach(d => { d.classList.remove("k"); d.style.background = ""; });
  people.forEach((p, i) => {
    const k = seed() < ctr / 100 * p.rel;
    setTimeout(() => { dots[i].style.background = k ? personColor(p) : `color-mix(in srgb, ${p.g === "F" ? css("--women") : css("--men")} 18%, var(--paper-2))`; if (k) dots[i].classList.add("k"); }, i * 1.2);
    if (k) { clicks++; const g = (p.g === "F" ? t("sim.w") : t("sim.m")) + " " + p.band; by[g] = (by[g] || 0) + 1; }
  });
  const top = Object.entries(by).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([g, n]) => `${g} (${n})`).join(", ");
  setTimeout(() => (outEl.innerHTML = t("sim.out", { k: clicks, e: fmt(ctr * 10, 1), top: top || t("sim.nobody") })), 1250);
}

/* ---------------- hero ---------------- */
function heroStats() {
  const v = D.validation, get = (m, k) => v.find(r => r.model.startsWith(m) && r.metric === k);
  const pc = get("PRODUCTION: CTR", "ctr"), pm = get("PRODUCTION: CTR", "cpm"), nc = get("naive", "ctr"), nm = get("naive", "cpm");
  $("#heroStats").innerHTML = [[fmt(pc.MAPE, 1) + "%", t("hero.s.ctr", { b: fmt(nc.MAPE, 1) })], [fmt(pm.MAPE, 1) + "%", t("hero.s.cpm", { b: fmt(nm.MAPE, 1) })],
    [pc.winners, t("hero.s.win")], [D.world ? D.world.companies : "–", t("hero.s.world")]].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
}
function heroCanvas() {
  const cv = $("#crowd"), ctx = cv.getContext("2d");
  let W2, H2, dots = [], mouse = { x: -1e4, y: -1e4 };
  const dpr = Math.min(2, window.devicePixelRatio || 1), r = rng(3);
  function size() {
    W2 = cv.clientWidth; H2 = cv.clientHeight; cv.width = W2 * dpr; cv.height = H2 * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.min(700, Math.floor(W2 * H2 / 2600)), pop = D.priors.population_it_millions, tot = Object.values(pop).reduce((a, b) => a + b, 0);
    dots = Array.from({ length: n }, () => {
      let u = r() * tot; const c = cells.find(k => (u -= pop[k]) <= 0) || cells[0];
      const age = c.endsWith("55+") ? 55 + r() * 20 : +c.split("|")[1].split("-")[0] + r() * 10;
      const x = W2 * (0.42 + r() * 0.58), y = r() * H2;
      return { x, y, hx: x, hy: y, g: c[0], r: 2 + (age - 18) / 22, ph: r() * 6.28 };
    });
  }
  size(); addEventListener("resize", size);
  cv.parentElement.addEventListener("mousemove", e => { const b = cv.getBoundingClientRect(); mouse = { x: e.clientX - b.left, y: e.clientY - b.top }; });
  cv.parentElement.addEventListener("mouseleave", () => (mouse = { x: -1e4, y: -1e4 }));
  let tt = 0;
  (function loop() {
    tt += 0.008; ctx.clearRect(0, 0, W2, H2);
    const cw = css("--women"), cm = css("--men");
    for (const d of dots) {
      const tx = d.hx + Math.sin(tt + d.ph) * 6, ty = d.hy + Math.cos(tt * 0.8 + d.ph) * 6, dx = d.x - mouse.x, dy = d.y - mouse.y, dist = Math.hypot(dx, dy);
      if (dist < 110) { d.x += dx / dist * (110 - dist) * 0.08; d.y += dy / dist * (110 - dist) * 0.08; }
      d.x += (tx - d.x) * 0.04; d.y += (ty - d.y) * 0.04;
      ctx.globalAlpha = 0.18 + 0.55 * Math.min(1, Math.max(0, (d.x - W2 * 0.38) / (W2 * 0.25))); ctx.fillStyle = d.g === "F" ? cw : cm;
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, 6.283); ctx.fill();
    }
    requestAnimationFrame(loop);
  })();
}

/* ---------------- switcher ---------------- */
function switcher() {
  $("#switcher").innerHTML = D.advertisers.map(a => `<button data-b="${a.id}" class="${a.id === state.brand ? "on" : ""}"><i style="background:${BRAND[a.id]}"></i>${a.name}<span class="vt">· ${t("vert." + a.vertical)}</span></button>`).join("");
}
function setBrand(b) {
  state.brand = b; state.adset = brandSets()[0].id; state.labCell = null; state.hidden.clear(); state.studioAud = brandSets()[0].id;
  document.documentElement.style.setProperty("--accent", BRAND[b]);
  renderBrand();
}

/* ---------------- audiences ---------------- */
function audiences() {
  const g = $("#audGrid"); g.innerHTML = "";
  for (const s of brandSets()) {
    const P = s.population, L = audLabel(P), warm = P.p_warm >= 0.7;
    const maxShare = Math.max(...cells.map(c => Math.max(P.cells[c].share, P.cells[c].prior)));
    const w = x => (x / maxShare * 100).toFixed(1) + "%";
    const pyr = D.priors.ages.slice().reverse().map(a => { const f = P.cells["F|" + a], m = P.cells["M|" + a];
      return `<div class="l"><div class="ghost" style="width:${w(f.prior)}"></div><div class="bar" data-w="${w(f.share)}" style="width:0"></div></div><div class="age">${a}</div>
              <div class="r"><div class="ghost" style="width:${w(m.prior)}"></div><div class="bar" data-w="${w(m.share)}" style="width:0"></div></div>`; }).join("");
    const moved = Math.max(Math.abs(P.shift_in_prior_sd.share_female), Math.abs(P.shift_in_prior_sd.mean_age));
    const prof = s.fingerprint.profile;
    const card = h("div", { class: "card aud reveal" + (s.id === state.adset ? " sel" : ""), "data-id": s.id }, `
      <div class="top"><span class="id">${s.id} · €${fmt(s.base_budget, 0)}${t("perday")}</span><span class="chip ${warm ? "warm" : ""}">${warm ? t("chip.warm") : P.p_warm <= 0.3 ? t("chip.cold") : t("chip.unclear")}</span></div>
      <h3>${cap(L.headline)}</h3><p class="vs">${L.vs.map(cap).join(" · ")}</p>
      <div class="pyr-head"><span>${t("women")}</span><span></span><span>${t("men")}</span></div><div class="pyramid">${pyr}</div>
      <div class="facts">
        <div class="fact"><b>${pct(P.share_female.mean)}</b><span>${t("f.women", { a: Math.round(P.share_female.p10 * 100), b: Math.round(P.share_female.p90 * 100) })}</span></div>
        <div class="fact"><b>${fmt(P.mean_age.mean, 0)}</b><span>${t("f.age", { a: fmt(P.mean_age.p10, 0), b: fmt(P.mean_age.p90, 0) })}</span></div>
        <div class="fact"><b>${fmt(s.fingerprint.ctr, 2)}%</b><span>${t("f.ctr", { x: fmt(P.observed.ctr_vs_advertiser, 2) })}</span></div>
        <div class="fact"><b>${eur(s.fingerprint.cpm)}</b><span>${t("f.cpm", { x: fmt(P.observed.cpm_vs_advertiser, 2) })}</span></div>
      </div>
      <div class="meter"><span>${t("prior")}</span><div class="track"><div class="fill" data-w="${Math.min(100, moved / 1.5 * 100).toFixed(0)}%" style="width:0"></div></div><span>${t("data")}</span></div>
      <p class="note" style="margin-top:6px">${L.conf}. ${t("freqnote", { f: fmt(s.fingerprint.frequency, 2), x: fmt(P.observed.frequency_vs_advertiser, 2) })}</p>
      <div class="behav"><b>${t("behav")}</b> ${t("beh." + prof + ".who")}<br><b>${t("alt")}</b> ${t("beh." + prof + ".alt")}</div>`);
    card.addEventListener("click", () => selectSet(s.id));
    g.appendChild(card);
  }
  setTimeout(() => $$("#audGrid [data-w]").forEach(b => (b.style.width = b.dataset.w)), 80);
  observe(); crowdPanel();
}
function selectSet(id) { state.adset = id; state.hidden.clear(); $$(".aud").forEach(x => x.classList.toggle("sel", x.dataset.id === id)); crowdPanel(); forecast(); whatif(); }

function crowdPanel() {
  const s = setById(state.adset), L = audLabel(s.population), people = crowd(s, 100, s.id.length * 31 + s.id.charCodeAt(s.id.length - 1));
  const ads = adsOf(s.id), fc = ads.map(a => mean(D.forecast[a.id].ctr)), best = ads[fc.indexOf(Math.max(...fc))];
  $("#crowdKicker").textContent = t("crowd.kicker", { id: s.id });
  $("#crowdTitle").innerHTML = t("crowd.title", { label: L.headline });
  $("#crowdLegend").innerHTML = `<span><i style="background:var(--women)"></i>${t("women")}</span><span><i style="background:var(--men)"></i>${t("men")}</span><span style="color:var(--ink-3)">${t("crowd.lighter")}</span>`;
  const g = $("#crowdGrid"); g.innerHTML = "";
  people.forEach((p, i) => {
    const d = h("div", { class: "person" }); d.style.background = personColor(p);
    d.addEventListener("mouseenter", () => { if (!best) return; const c = creative(best.creative);
      $("#persona").innerHTML = t("persona", { who: p.g === "F" ? t("woman") : t("man"), age: p.age, band: p.band, hl: esc(c.headline), lever: lever(c.lever), fmt: fmtName(c.format),
        ctr: fmt(mean(D.forecast[best.id].ctr) * p.rel, 2), rel: p.rel >= 1 ? t("more", { x: fmt(p.rel, 2) }) : t("less", { x: fmt(1 / p.rel, 2) }) }); });
    g.appendChild(d); setTimeout(() => d.classList.add("in"), 6 * i);
  });
  $("#persona").innerHTML = `<span style="color:var(--ink-3)">${t("crowd.hover")}</span>`;
}

/* ---------------- forecast chart ---------------- */
function forecast() {
  $("#fcSets").innerHTML = brandSets().map(s => `<button class="pill ${s.id === state.adset ? "on" : ""}" data-s="${s.id}">${s.id.split("-")[1]} · ${audLabel(s.population).short}</button>`).join("");
  const svg = $("#fcChart"), W = svg.clientWidth || 900, H = svg.clientHeight || 420, m = { l: 48, r: 16, t: 26, b: 30 };
  svg.innerHTML = ""; svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const ads = adsOf(state.adset), k = state.kpi, start = "2026-10-12", end = "2026-11-30";
  const t0 = new Date(start).getTime(), t1 = new Date(end).getTime();
  const X = d => m.l + (new Date(d).getTime() - t0) / (t1 - t0) * (W - m.l - m.r);
  const series = ads.map((a, i) => { const hst = D.history[a.id] || { d: [], ctr: [], cpm: [] }, f = D.forecast[a.id];
    return { a, color: AD_COLORS[i % AD_COLORS.length], hist: hst.d.map((d, j) => [d, hst[k][j]]).filter(([d]) => d >= start), f: f.d.map((d, j) => [d, f[k][j], f[k + "_lo"][j], f[k + "_hi"][j]]) }; });
  const vis = series.filter(s => !state.hidden.has(s.a.id));
  const vals = vis.flatMap(s => [...s.hist.map(x => x[1]), ...s.f.flatMap(x => [x[2], x[3]])]).filter(isFinite);
  let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.08; lo = Math.max(0, lo - pad); hi += pad;
  const Y = v => H - m.b - (v - lo) / (hi - lo) * (H - m.t - m.b);
  const grid = svgEl("g", { class: "grid" }); svg.appendChild(grid);
  for (let i = 0; i <= 4; i++) { const v = lo + (hi - lo) * i / 4, y = Y(v); grid.appendChild(svgEl("line", { x1: m.l, x2: W - m.r, y1: y, y2: y }));
    const tx = svgEl("text", { x: m.l - 8, y: y + 4, "text-anchor": "end" }); tx.textContent = k === "ctr" ? fmt(v, 2) + "%" : "€" + fmt(v, 1); grid.appendChild(tx); }
  ["2026-10-15", "2026-11-01", "2026-11-16", "2026-11-30"].forEach(d => { const tx = svgEl("text", { x: X(d), y: H - 8, "text-anchor": "middle" }); tx.textContent = dshort(d); svg.appendChild(tx); });
  const fx = X("2026-11-16");
  svg.appendChild(svgEl("rect", { x: fx, y: m.t, width: W - m.r - fx, height: H - m.t - m.b, fill: "var(--band)", opacity: .5, rx: 8 }));
  const ft = svgEl("text", { x: fx + 8, y: m.t + 14 }); ft.textContent = t("fc.forecast"); svg.appendChild(ft);
  const ev = svgEl("g", { class: "event" }); svg.appendChild(ev);
  const EVN = ["Halloween", "Singles Day", "Inizio Black Week", "Black Friday", "Cyber Monday"];
  D.calendar.filter(e => e.data >= start).forEach(e => {
    const key = EVN.find(n => e.evento.startsWith(n)); if (!key) return;
    const x = X(e.data), right = x > W - 140; ev.appendChild(svgEl("line", { x1: x, x2: x, y1: m.t, y2: H - m.b }));
    const tx = svgEl("text", { x: right ? x - 4 : x + 4, y: m.t - 8 + (key === "Black Friday" ? 14 : 0), "text-anchor": right ? "end" : "start" }); tx.textContent = t("ev." + key); ev.appendChild(tx);
  });
  const path = pts => pts.map((p, j) => (j ? "L" : "M") + X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1)).join("");
  for (const s of vis) {
    svg.appendChild(svgEl("path", { d: path(s.f.map(p => [p[0], p[3]]).concat(s.f.map(p => [p[0], p[2]]).reverse())) + "Z", fill: s.color, opacity: .10 }));
    svg.appendChild(svgEl("path", { d: path(s.hist.filter(p => isFinite(p[1]))), fill: "none", stroke: s.color, "stroke-width": 1.4, opacity: .55 }));
    const fl = svgEl("path", { d: path(s.f.map(p => [p[0], p[1]])), fill: "none", stroke: s.color, "stroke-width": 2.4, "stroke-linecap": "round" });
    fl.style.strokeDasharray = 2000; fl.style.strokeDashoffset = 2000; fl.style.transition = "stroke-dashoffset 1.4s cubic-bezier(.2,.7,.2,1)";
    svg.appendChild(fl); requestAnimationFrame(() => requestAnimationFrame(() => (fl.style.strokeDashoffset = 0)));
  }
  const cross = svgEl("line", { y1: m.t, y2: H - m.b, stroke: "var(--ink)", "stroke-width": 1, opacity: 0 }); svg.appendChild(cross);
  const tip = $("#fcTip"), dot = c => `<span style="color:${c === "var(--ink)" ? "inherit" : c}">●</span>`;
  svg.onmousemove = e => {
    const b = svg.getBoundingClientRect(), px = (e.clientX - b.left) * W / b.width, tm = t0 + (px - m.l) / (W - m.l - m.r) * (t1 - t0); if (tm < t0 || tm > t1) return;
    const d = new Date(Math.round(tm / 864e5) * 864e5).toISOString().slice(0, 10);
    cross.setAttribute("x1", X(d)); cross.setAttribute("x2", X(d)); cross.setAttribute("opacity", .25);
    const val = v => k === "ctr" ? fmt(v, 2) + "%" : eur(v);
    const rows = vis.map(s => { const f = s.f.find(p => p[0] === d), hh = s.hist.find(p => p[0] === d);
      if (f) return `${dot(s.color)} ${s.a.id.split("-")[1]} <b>${val(f[1])}</b> <span style="opacity:.6">${fmt(f[2], k === "ctr" ? 2 : 1)}–${fmt(f[3], k === "ctr" ? 2 : 1)}</span>`;
      if (hh) return `${dot(s.color)} ${s.a.id.split("-")[1]} ${val(hh[1])} <span style="opacity:.6">${t("fc.actual")}</span>`; return ""; }).filter(Boolean);
    if (!rows.length) { tip.style.opacity = 0; return; }
    const e2 = D.calendar.find(x => x.data === d);
    tip.innerHTML = `<b>${dshort(d)}</b>${e2 ? " · " + e2.evento : ""}<br>` + rows.join("<br>"); tip.style.opacity = 1;
    const cb = $(".chart-card").getBoundingClientRect(); let left = e.clientX - cb.left + 16; if (left > cb.width - 240) left -= 260;
    tip.style.left = left + "px"; tip.style.top = (e.clientY - cb.top - 20) + "px";
  };
  svg.onmouseleave = () => { tip.style.opacity = 0; cross.setAttribute("opacity", 0); };
  $("#fcLegend").innerHTML = series.map(s => `<span data-a="${s.a.id}" class="${state.hidden.has(s.a.id) ? "off" : ""}"><i style="background:${s.color}"></i>${s.a.id}${D.forecast[s.a.id].cold ? " · " + t("fc.new") : ""}</span>`).join("") + `<span style="cursor:default;color:var(--ink-3)">${t("fc.legend")}</span>`;
  $("#fcTable").innerHTML = series.map(s => { const c = creative(s.a.creative), f = D.forecast[s.a.id];
    return `<div class="adrow"><div class="h"><span><span class="sw" style="background:${s.color}"></span><b>${s.a.id}</b></span><span class="chip ${f.cold ? "warm" : ""}">${f.cold ? t("fc.newchip") : lever(c.lever)}</span></div>
      <p>“${esc(c.headline)}”</p><div class="nums"><span>CTR <b>${fmt(mean(f.ctr), 2)}%</b></span><span>CPM <b>${eur(mean(f.cpm))}</b></span><span>${fmtName(c.format)}</span></div></div>`; }).join("");
}

/* ---------------- decide ---------------- */
function whatif() {
  const s = setById(state.adset), ads = adsOf(s.id);
  const full = ads.reduce((x, a) => D.forecast[a.id].d.length > D.forecast[x.id].d.length ? a : x, ads[0]);
  const days = D.forecast[full.id].d, B = D.forecast[full.id].budget;
  const onDay = (d, k) => ads.map(a => { const f = D.forecast[a.id], j = f.d.indexOf(d); return j < 0 ? null : f[k][j]; }).filter(v => v != null && isFinite(v));
  const ctr0 = mean(days.map(d => mean(onDay(d, "ctr")))), cpm0 = mean(days.map(d => mean(onDay(d, "cpm"))));
  const b0 = mean(B), kC = D.engine.k_cpm, kT = D.engine.k_ctr;
  const seen = s.budget.d.map((d, j) => [d, s.budget.eur[j]]).filter(([d]) => d <= "2026-11-15").map(x => x[1]);
  const seenMax = Math.max(...seen), seenMin = Math.min(...seen);
  const at = b => { const cpm = cpm0 * Math.pow(b / b0, kC), ctr = ctr0 * Math.pow(b / b0, kT), clk = b / cpm * 1000 * ctr / 100; return { cpm, ctr, clk, cpc: b / clk }; };
  const base = at(b0);
  $("#whatif").innerHTML = `<div class="row"><h4 style="margin:0">${t("wi.title")}</h4><select id="wiSet">${brandSets().map(x => `<option ${x.id === s.id ? "selected" : ""}>${x.id}</option>`).join("")}</select></div>
    <div class="big-budget" id="wiB"></div><input type="range" id="wiR" min="0.25" max="3" step="0.01" value="1" aria-label="budget">
    <div class="kpis" id="wiK"></div><div class="flag" id="wiF"></div><svg id="wiCurve" class="chart" style="height:150px;margin-top:10px"></svg>
    <p class="note">${t("wi.note", { b: eur(b0, 0), k: fmt(kC, 2), kc: fmt(kT, 2) })}</p>`;
  $("#wiSet").onchange = e => selectSet(e.target.value);
  const curve = $("#wiCurve"), W = curve.clientWidth || 600, H = 150, m = { l: 40, r: 10, t: 10, b: 22 };
  curve.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const xs = Array.from({ length: 60 }, (_, i) => 0.25 + i * 2.75 / 59), ys = xs.map(x => at(b0 * x).clk), yM = Math.max(...ys);
  const X = x => m.l + (x - 0.25) / 2.75 * (W - m.l - m.r), Y = y => H - m.b - y / yM * (H - m.t - m.b);
  const sx0 = X(Math.max(0.25, seenMin / b0)), sx1 = X(Math.min(3, seenMax / b0));
  curve.innerHTML = `<rect x="${sx0}" y="${m.t}" width="${Math.max(2, sx1 - sx0)}" height="${H - m.t - m.b}" fill="var(--band)" rx="6"/>
    <text x="${(sx0 + sx1) / 2}" y="${m.t + 12}" text-anchor="middle">${t("wi.seen")}</text>
    <path d="${xs.map((x, i) => (i ? "L" : "M") + X(x) + "," + Y(ys[i])).join("")}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>
    <text x="${m.l - 6}" y="${Y(yM) + 4}" text-anchor="end">${fmt(yM, 0)}</text><text x="${m.l - 6}" y="${H - m.b}" text-anchor="end">0</text>
    <text x="${X(1)}" y="${H - 6}" text-anchor="middle">${t("wi.planlbl")}</text><text x="${X(0.25)}" y="${H - 6}">0.25×</text><text x="${X(3)}" y="${H - 6}" text-anchor="end">3×</text>
    <circle id="wiDot" r="6" fill="var(--card)" stroke="var(--ink)" stroke-width="2"/>`;
  const upd = () => {
    const x = +$("#wiR").value, b = b0 * x, o = at(b);
    const dlt = (a, c, inv) => { const p = (a / c - 1) * 100, good = inv ? p < 0 : p > 0; return `<span class="d ${Math.abs(p) < .5 ? "" : good ? "up" : "down"}">${p >= 0 ? "+" : ""}${fmt(p, 0)}%</span>`; };
    $("#wiB").innerHTML = `€${fmt(b, 0)}<small> ${t("perday")} · ${fmt(x, 2)}${t("wi.plan")}</small>`;
    $("#wiK").innerHTML = [[fmt(o.clk, 0), t("wi.clicks"), dlt(o.clk, base.clk)], [eur(o.cpc), t("wi.cpc"), dlt(o.cpc, base.cpc, true)], [eur(o.cpm), "CPM", dlt(o.cpm, base.cpm, true)], [fmt(o.ctr, 2) + "%", "CTR", dlt(o.ctr, base.ctr)]]
      .map(([v, l, d]) => `<div class="kpi"><b>${v}</b><span>${l}</span> ${d}</div>`).join("");
    $("#wiF").textContent = b > seenMax * 1.02 ? t("wi.above", { b: eur(seenMax, 0) }) : b < seenMin * 0.98 ? t("wi.below", { b: eur(seenMin, 0) }) : "";
    const dt = $("#wiDot"); dt.setAttribute("cx", X(x)); dt.setAttribute("cy", Y(o.clk));
  };
  $("#wiR").oninput = upd; upd(); moves();
}
function moves() {
  const rows = D.decisions.budget.filter(r => r.campaign_id === adv(state.brand).campaign), mx = Math.max(...rows.flatMap(r => [r.budget, r.budget_proposed]));
  const cr = D.decisions.creative.filter(r => r.adset_id.startsWith(state.brand) && r.week.startsWith("Black"));
  $("#moves").innerHTML = `<h4>${t("mv.title")}</h4>` + rows.map(r => { const d = r.budget_proposed - r.budget;
    return `<div class="move"><span class="id">${r.adset_id}</span><div class="bar"><i style="left:0;width:${r.budget / mx * 100}%;background:var(--line)"></i><i style="left:0;width:${r.budget_proposed / mx * 100}%;background:${d >= 0 ? "var(--sage)" : "var(--women)"};opacity:.85;height:50%;top:25%"></i></div><span class="arrow ${d >= 0 ? "up" : "down"}">${d >= 0 ? "+" : "−"}€${fmt(Math.abs(d), 0)}</span></div>`; }).join("")
    + `<p class="note">${t("mv.note", { g: fmt(rows[0].campaign_gain_clicks_per_day, 1), a: fmt(rows[0].gain_elasticity_min, 1), b: fmt(rows[0].gain_elasticity_max, 1), c: fmt(rows[0].gain_adverse_kpi_min, 1) })}</p>
    <h4 style="margin-top:22px">${t("mv.cr")}</h4>` + cr.map(r => `<div class="move"><span class="id">${r.adset_id}</span><span>${t("mv.push")} <b>${r.push_asset}</b> (${lever(r.push_leva)}, ${fmt(r.push_ctr, 2)}%)${r.push_is_cold_start ? " · " + t("fc.new") : ""}<br><span style="color:var(--ink-3)">${t("mv.pause")} ${r.pause_asset} (${fmt(r.pause_ctr, 2)}%)</span></span><span class="arrow">${r.ctr_gap}</span></div>`).join("");
  timing();
}
function timing() {
  const tm = D.decisions.timing, W = $("#timing").clientWidth - 48 || 900, H = 160, m = { l: 44, r: 10, t: 16, b: 24 };
  const v = tm.map(x => x.cpc), lo = Math.min(...v) * 0.95, hi = Math.max(...v) * 1.05;
  const X = i => m.l + i / (tm.length - 1) * (W - m.l - m.r), Y = y => H - m.b - (y - lo) / (hi - lo) * (H - m.t - m.b);
  const best = v.indexOf(Math.min(...v)), worst = v.indexOf(Math.max(...v));
  $("#timing").innerHTML = `<div class="row" style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px"><h4 style="margin:0">${t("tm.title")}</h4><span class="note" style="margin:0">${t("tm.range", { a: dshort(tm[best].data), ca: eur(v[best]), b: dshort(tm[worst].data), cb: eur(v[worst]) })}</span></div>
  <svg class="chart" viewBox="0 0 ${W} ${H}" style="height:${H}px"><path d="${tm.map((x, i) => (i ? "L" : "M") + X(i) + "," + Y(x.cpc)).join("")}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>
    ${tm.map((x, i) => `<circle cx="${X(i)}" cy="${Y(x.cpc)}" r="${i === best || i === worst ? 5 : 2.5}" fill="${i === best ? "var(--sage)" : i === worst ? "var(--women)" : "var(--accent)"}"/>`).join("")}
    ${tm.map((x, i) => i % 2 === 0 ? `<text x="${X(i)}" y="${H - 6}" text-anchor="middle">${dshort(x.data)}</text>` : "").join("")}
    <text x="${m.l - 6}" y="${Y(hi) + 10}" text-anchor="end">€${fmt(hi, 2)}</text><text x="${m.l - 6}" y="${Y(lo)}" text-anchor="end">€${fmt(lo, 2)}</text></svg>
  <p class="note">${t("tm.note")}</p>`;
}

/* ---------------- creative lab ---------------- */
function lab() {
  const sets = brandSets(), cr = D.creatives.filter(c => c.id.startsWith(state.brand));
  const cell = (a, c) => D.lab.find(x => x.audience === a && x.creative === c);
  const live = new Set(D.ads.filter(a => D.forecast[a.id]).map(a => a.adset + "|" + a.creative));
  const vals = D.lab.filter(x => x.audience.startsWith(state.brand)).map(x => x.ctr), lo = Math.min(...vals), hi = Math.max(...vals);
  const col = v => `color-mix(in srgb, var(--accent) ${Math.round(8 + 80 * (v - lo) / (hi - lo))}%, var(--paper-2))`;
  $("#heat").innerHTML = `<table><tr><th>${t("lab.creative")}</th>${sets.map(s => `<th>${s.id.split("-")[1]}<br><span class="lv">${audLabel(s.population).short}</span></th>`).join("")}</tr>` +
    cr.map(c => `<tr><th>${c.id.split("-")[1]} <span class="lv">${lever(c.lever)} · ${fmtName(c.format)}</span></th>${sets.map(s => { const x = cell(s.id, c.id); if (!x) return "<td></td>";
      const dark = (x.ctr - lo) / (hi - lo) > .55; return `<td class="c ${live.has(s.id + "|" + c.id) ? "live" : ""}" data-a="${s.id}" data-c="${c.id}" style="background:${col(x.ctr)};color:${dark ? "var(--paper)" : "var(--ink)"}">${fmt(x.ctr, 2)}%</td>`; }).join("")}</tr>`).join("") +
    `</table><p class="note">${t("lab.note")}</p>`;
  $$("#heat td.c").forEach(td => td.addEventListener("click", () => { state.labCell = [td.dataset.a, td.dataset.c]; labDetail(); }));
  if (!state.labCell) { const b = D.lab.filter(x => x.audience.startsWith(state.brand)).sort((a, b) => b.ctr - a.ctr)[0]; state.labCell = [b.audience, b.creative]; }
  labDetail();
}
function labDetail() {
  const [a, c] = state.labCell, x = D.lab.find(y => y.audience === a && y.creative === c), cr = creative(c), s = setById(a);
  $$("#heat td.c").forEach(td => td.classList.toggle("sel", td.dataset.a === a && td.dataset.c === c));
  $("#labDetail").innerHTML = `<p class="kicker" style="margin-bottom:6px">${t("lab.in", { c, a })}</p><h3>${fmt(x.ctr, 2)}% <span style="font-size:18px;color:var(--ink-3)">CTR · 80%: ${fmt(x.ctr_lo, 2)}–${fmt(x.ctr_hi, 2)}</span></h3>
    <p class="note" style="margin-top:0">${t("lab.meta", { cpm: eur(x.cpm), cpc: eur(x.cpm / (10 * x.ctr)), aud: audLabel(s.population).headline })}</p>
    <div class="copy"><div class="hl">${esc(cr.headline)}</div><p>${esc(cr.body)}</p><p><b>${esc(cr.cta)}</b> · ${lever(cr.lever)} · ${fmtName(cr.format)}${cr.video_s ? " · " + cr.video_s + "s" : ""}</p><p style="color:var(--ink-3)">${t("lab.visual")} ${esc(cr.visual)}</p></div>
    <button class="btn" id="simBtn">${t("sim.btn")}</button><div class="mini-crowd" id="mini"></div><div class="sim-out" id="simOut"></div>`;
  const people = crowd(s, 1000, 11); $("#mini").innerHTML = people.map(() => "<i></i>").join("");
  $("#simBtn").onclick = () => runCrowd($("#mini"), $("#simOut"), people, x.ctr);
}

/* ---------------- creative studio ---------------- */
function studioSteps() {
  $("#stSteps").innerHTML = [1, 2, 3, 4].map(i => `<li><span class="n">${i}</span><b>${t("st.s" + i)}</b><span>${t("st.s" + i + "d")}</span></li>`).join("");
}
function studio() {
  studioSteps();
  if (!state.studioAud || !state.studioAud.startsWith(state.brand)) state.studioAud = brandSets()[0].id;
  const run = state.runs[state.studioAud], br = (run && run.brief) || (D.studio_briefs || {})[state.brand] || {};
  const mode = state.live && state.live.ok ? (state.live.key ? "live" : "nokey") : "static";
  $("#brief").innerHTML = `
    <div class="mode ${mode}">${mode === "live" ? t("st.live", { m: state.live.model }) : t("st.static")}</div>
    <label>${t("st.audience")}<select name="audience">${brandSets().map(s => `<option value="${s.id}" ${s.id === state.studioAud ? "selected" : ""}>${s.id} · ${audLabel(s.population).short}</option>`).join("")}</select></label>
    <label>${t("st.product")}<textarea name="product" rows="3">${esc(br.product || "")}</textarea></label>
    <label>${t("st.offer")}<textarea name="offer" rows="2">${esc(br.offer || "")}</textarea></label>
    <div class="two"><label>${t("st.maxd")}<input name="max_discount_pct" type="number" min="0" max="90" value="${br.max_discount_pct ?? ""}"></label>
    <label>${t("st.n")}<input name="n" type="number" min="2" max="8" value="6"></label></div>
    <label>${t("st.notes")}<input name="notes" value="${esc(br.notes || "")}"></label>
    ${mode === "live" ? `<button class="btn" type="submit" id="genBtn">${t("st.gen")}</button>` : `<p class="note">${mode === "nokey" ? t("st.nokey") : t("st.staticnote")}</p>`}
    <div class="progress" id="stProg"></div>`;
  $("#brief [name=audience]").onchange = e => { state.studioAud = e.target.value; studio(); };
  $("#brief").onsubmit = e => { e.preventDefault(); generate(); };
  studioResults();
}
async function generate() {
  const f = new FormData($("#brief")), body = Object.fromEntries(f.entries());
  body.brand = state.brand; body.n = +body.n || 6; if (body.max_discount_pct === "") body.max_discount_pct = null;
  const prog = $("#stProg"), btn = $("#genBtn"); btn.disabled = true; prog.innerHTML = `<span class="spin"></span>${t("st.p1")}`;
  const tm = setTimeout(() => (prog.innerHTML = `<span class="spin"></span>${t("st.p2")}`), 25000);
  try {
    const r = await fetch("/api/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json(); if (!r.ok) throw new Error(j.error || r.status);
    state.runs[j.audience] = j; state.studioAud = j.audience; prog.innerHTML = ""; studio();
  } catch (e) { prog.innerHTML = `<span class="err">${esc(t("st.err", { e: e.message }))}</span>`; }
  finally { clearTimeout(tm); if (btn) btn.disabled = false; }
}
function studioResults() {
  const run = state.runs[state.studioAud], s = setById(state.studioAud);
  if (!run) { $("#stEvidence").innerHTML = `<p class="note" style="margin:0">${t("st.none")}</p>`; $("#stCands").innerHTML = ""; return; }
  const ev = run.evidence, L = Object.entries(ev.lever_forecast_ctr), best = ev.best_existing[0] || {};
  $("#stEvidence").innerHTML = `<p style="margin:0">${t("st.ev", { a: state.studioAud, l1: lever(L[0][0]), c1: fmt(L[0][1], 2), l2: lever(L[1]?.[0]), c2: fmt(L[1]?.[1], 2), l3: lever(L[2]?.[0]), c3: fmt(L[2]?.[1], 2), b: best.creative_id, bc: fmt(ev.benchmark_ctr, 2) })}</p>
    <p class="note">${t("st.meta", { m: run.meta.model, s: fmt(run.meta.seconds, 0), t: (run.meta.input_tokens + run.meta.output_tokens).toLocaleString(loc()), d: new Date(run.generated_at).toLocaleString(loc(), { dateStyle: "medium", timeStyle: "short" }) })}</p>`;
  const ok = run.candidates.filter(c => c.target), all = ok.flatMap(c => [c.target.ctr_lo, c.target.ctr_hi]).concat([ev.benchmark_ctr]);
  const lo = Math.min(...all) * 0.9, hi = Math.max(...all) * 1.05, P = v => ((v - lo) / (hi - lo) * 100).toFixed(1) + "%";
  const people = crowd(s, 1000, 23);
  $("#stCands").innerHTML = run.candidates.map((c, i) => {
    const fl = (c.flags || []).map(f => `<span class="flag-chip ${f.reject ? "bad" : ""}">${esc(t("st.fl." + f.code, { f: f.found, m: f.max, field: f.field ? t("field." + f.field) : "", len: f.len, lo: f.lo, hi: f.hi, set: f.set, nums: (f.nums || []).join(", ") }))}</span>`).join("")
      + (c.duplicate_of != null ? `<span class="flag-chip">${t("st.dup", { k: c.duplicate_of + 1 })}</span>` : "");
    if (!c.target) return `<div class="cand rejected card"><div class="ch"><span class="rk">×</span><div><span class="chip">${t("st.rejected")}</span> ${fl}</div></div><div class="hl">${esc(c.headline)}</div></div>`;
    const ba = c.by_audience.slice().sort((a, b) => b.ctr - a.ctr)[0], verdict = c.clearly_better ? "better" : c.target.ctr_hi < ev.benchmark_ctr ? "below" : "within";
    return `<div class="cand card reveal" data-i="${i}">
      <div class="ch"><span class="rk">${c.rank}</span><div class="chips"><span class="chip">${lever(c.leva)}</span><span class="chip">${fmtName(c.formato)}${c.durata_video_s ? " · " + c.durata_video_s + "s" : ""}</span><span class="chip nov-${c.novelty}">${t("st.nov." + c.novelty)}</span>${fl}</div></div>
      <div class="cbody"><div class="copy"><div class="hl">${esc(c.headline)}</div><p>${esc(c.testo_principale)}</p><p><b>${esc(c.call_to_action)}</b></p><p class="vis">${t("lab.visual")} ${esc(c.descrizione_visual)}</p></div>
      <div class="score"><span class="lbl">${t("st.target", { a: state.studioAud })}</span><b>${fmt(c.target.ctr, 2)}%</b><span class="lbl">80%: ${fmt(c.target.ctr_lo, 2)}–${fmt(c.target.ctr_hi, 2)} · CPC ${eur(c.target.cpc)}</span>
        <div class="range"><i class="band" style="left:${P(c.target.ctr_lo)};width:calc(${P(c.target.ctr_hi)} - ${P(c.target.ctr_lo)})"></i><i class="pt" style="left:${P(c.target.ctr)}"></i><i class="bench" style="left:${P(ev.benchmark_ctr)}"></i></div>
        <span class="lbl bl">┆ ${t("st.bench")} ${best.creative_id} ${fmt(ev.benchmark_ctr, 2)}%</span>
        <span class="verdict ${verdict}">${t("st." + verdict)}</span>
        <span class="lbl">${t("st.bestaud", { a: ba.audience, c: fmt(ba.ctr, 2) })}</span></div></div>
      <details class="why"><summary>${t("st.why")}</summary><p>${esc(LANG === "it" ? c.rationale_it : c.rationale_en)}</p></details>
      <button class="btn ghost" data-sim="${i}">${t("sim.btn")}</button><div class="mini-crowd" data-mc="${i}"></div><div class="sim-out" data-so="${i}"></div></div>`; }).join("");
  $$("#stCands [data-sim]").forEach(b => b.onclick = () => { const i = b.dataset.sim, c = run.candidates[i], mc = $(`[data-mc="${i}"]`);
    if (!mc.children.length) mc.innerHTML = people.map(() => "<i></i>").join("");
    runCrowd(mc, $(`[data-so="${i}"]`), people, c.target.ctr); });
  observe();
}
async function detectLive() {
  if (!location.protocol.startsWith("http")) return;
  try { const r = await fetch("/api/health", { cache: "no-store" }); if (r.ok) { state.live = await r.json(); studio(); } } catch (e) {}
}

/* ---------------- proof ---------------- */
function proof() {
  const W = D.world;
  if (!W) { $("#proofGrid").innerHTML = `<div class="card">${t("pf.run")}</div>`; return; }
  const f = W.forecast, a = W.audience, b = W.budget_elasticity;
  $("#proofGrid").innerHTML = [
    [W.companies, t("pf.c1"), t("pf.c1n", { s: W.by_scale.small, m: W.by_scale.medium, l: W.by_scale.large, a: W.audiences })],
    [f.engine_beats_naive_ctr, t("pf.c2"), t("pf.c2n", { a: fmt(f.ctr_log_err_engine, 3), b: fmt(f.ctr_log_err_naive, 3) })],
    [f.engine_beats_naive_cpm, t("pf.c3"), t("pf.c3n", { a: fmt(f.cpm_log_err_engine, 3), b: fmt(f.cpm_log_err_naive, 3) })],
    [pct(f.cov80_cpm_known), t("pf.c4"), t("pf.c4n", { a: pct(f.cov80_cpm_new), b: pct(f.cov80_ctr_known), c: pct(f.cov80_ctr_new) })],
    [pct(a.warm_detection_accuracy), t("pf.c5"), t("pf.c5n", { a: pct(a.warm_recall), b: pct(a.warm_false_alarm) })],
    [fmt(b.with_budget_changes_abs_err, 3), t("pf.c6"), t("pf.c6n", { a: fmt(b.without_budget_changes_abs_err, 3), b: fmt(b.prior_only_abs_err, 3) })],
  ].map(([v, s, n]) => `<div class="card pf reveal"><span>${s}</span><b>${v}</b><small>${n}</small></div>`).join("");
  scatter("#scatterF", D.world_audiences || [], "female_true", "female_est", 0, 1, v => Math.round(v * 100) + "%");
  scatter("#scatterA", D.world_audiences || [], "age_true", "age_est", 25, 60, v => Math.round(v));
  $("#scatterFNote").textContent = t("pf.sfn", { a: fmt(a.female_rmse_model * 100, 1), b: fmt(a.female_rmse_prior_only * 100, 1) });
  $("#scatterANote").textContent = t("pf.san", { a: fmt(a.age_rmse_model, 1), b: fmt(a.age_rmse_prior_only, 1), c: pct(a.age_cov80) });
  const v = D.validation, rows = [["naive last-7d", "naive"], ["tree +index", "tree"], ["ridge +index", "ridge"], ["PRODUCTION: CTR", "ours"]];
  $("#validTable").innerHTML = `<h4>${t("pf.tbl")}</h4><table><tr><th>${t("pf.model")}</th><th>${t("pf.ctr")}</th><th>${t("pf.win")}</th><th>${t("pf.cpm")}</th></tr>` +
    rows.map(([k, n]) => { const c = v.find(r => r.model.startsWith(k) && r.metric === "ctr"), p = v.find(r => r.model.startsWith(k) && r.metric === "cpm");
      return `<tr class="${n === "ours" ? "best" : ""}"><td>${t("pf.m." + n)}</td><td>${fmt(c.MAPE, 1)}%</td><td>${c.winners}</td><td>${fmt(p.MAPE, 1)}%</td></tr>`; }).join("") + `</table><p class="note">${t("pf.tnote")}</p>`;
  observe();
}
function scatter(sel, pts, kx, ky, lo, hi, lab2) {
  const svg = $(sel), W = svg.clientWidth || 400, H = 300, m = { l: 40, r: 10, t: 10, b: 28 };
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const X = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r), Y = v => H - m.b - (v - lo) / (hi - lo) * (H - m.t - m.b), cl = v => Math.min(hi, Math.max(lo, v));
  const vc = { beauty_skincare: BRAND.NDL, pet_ecommerce: BRAND.CDF, abbigliamento: BRAND.FGR };
  svg.innerHTML = `<line x1="${X(lo)}" y1="${Y(lo)}" x2="${X(hi)}" y2="${Y(hi)}" stroke="var(--line)" stroke-width="1.5"/>` +
    [lo, (lo + hi) / 2, hi].map(v => `<text x="${X(v)}" y="${H - 8}" text-anchor="middle">${lab2(v)}</text><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${lab2(v)}</text>`).join("") +
    pts.map(p => `<circle cx="${X(cl(p[kx]))}" cy="${Y(cl(p[ky]))}" r="3.6" fill="${vc[p.vertical]}" opacity=".7"/>`).join("") + `<text x="${W - m.r}" y="${m.t + 10}" text-anchor="end">${t("pf.axis")}</text>`;
}

/* ---------------- sources ---------------- */
function sources() {
  const P = D.priors, V = P.verticals, wb = Math.round(Object.entries(V.beauty_skincare.mean).filter(([k]) => k[0] === "F").reduce((s, [, x]) => s + x, 0) * 100);
  const S = [
    [1, {}, "https://affectgroup.com/blog/italy-facebook-instagram-audience-in-meta-ads-2026/", "Affectgroup, Mar 2026", "real"],
    [2, { n: V.beauty_skincare.n_ads, w: wb }, "https://www.facebook.com/ads/library/", "Meta Ad Library", "real"],
    [3, { n: V.pet_ecommerce.n_ads }, "https://www.facebook.com/ads/library/", "Meta Ad Library", "real"],
    [4, { n: V.abbigliamento.n_ads }, "https://www.facebook.com/ads/library/", "Meta Ad Library", "real"],
    [5, { a: fmt(Math.exp(P.kaggle_effects.ctr_log_female.estimate), 2), b: fmt(Math.exp(P.kaggle_effects.cpm_log_female.estimate), 2) }, "https://www.kaggle.com/datasets/loveall/clicks-conversion-tracking", "Kaggle", "real"],
    [6, { a: fmt(P.cross_checks.cpm_female_over_male.kaggle_adjusted, 2), b: fmt(P.cross_checks.cpm_female_over_male.lebesgue_2025, 2) }, "https://lebesgue.io/facebook-ads/facebook-cpm-by-gender", "Lebesgue 2025", "bench"],
    [7, {}, "https://wordstream.com/blog/facebook-ads-benchmarks-2025", "WordStream 2025", "bench"],
    [8, { a: fmt(P.bf_week_cpm_vs_september.kit_2025_index.beauty_skincare, 2), b: fmt(P.bf_week_cpm_vs_september.lebesgue_2025, 2), c: fmt(P.bf_week_cpm_vs_september.lebesgue_2024, 2) }, "https://lebesgue.io/?p=15192", "Lebesgue · Nest Commerce", "bench"],
    [9, {}, "https://lebesgue.io/?p=3128", "Lebesgue", "bench"],
    [10, { m: (Object.values(state.runs)[0] || {}).meta?.model || "Claude · OpenRouter · Ollama" }, "https://openrouter.ai/models?q=free", "OpenRouter · Anthropic", "bench"],
    [11, {}, "#proof", "↓", "assume"],
  ];
  $("#sourceList").innerHTML = S.map(([i, v, url, lbl, tag]) => `<div class="card src reveal"><span class="k">${t("so." + i + "k")}</span><h4>${t("so." + i + "t", v)}</h4><p>${t("so." + i + "p", v)}</p><a href="${url}" target="_blank" rel="noopener">${lbl} ↗</a><br><span class="tag ${tag}">${t("tag." + tag)}</span></div>`).join("");
  $("#limits").innerHTML = `<h4>${t("so.lim")}</h4><ul>${[1, 2, 3, 4, 5, 6].map(i => `<li>${t("so.l" + i)}</li>`).join("")}</ul>`;
  observe();
}

/* ---------------- plumbing ---------------- */
let io;
function observe() { io = io || new IntersectionObserver(es => es.forEach(e => e.isIntersecting && e.target.classList.add("in")), { threshold: 0, rootMargin: "0px 0px -6% 0px" }); $$(".reveal:not(.in)").forEach(e => io.observe(e)); }
function renderBrand() { switcher(); audiences(); forecast(); whatif(); lab(); studio(); }
function renderAll() { applyStatic(); heroStats(); renderBrand(); proof(); sources(); }

function init() {
  $("#switcher").addEventListener("click", e => { const b = e.target.closest("button"); if (b) setBrand(b.dataset.b); });
  $("#lang").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; LANG = b.dataset.l; store.set("lang", LANG); renderAll(); });
  $("#fcSets").addEventListener("click", e => { const b = e.target.closest(".pill"); if (b) selectSet(b.dataset.s); });
  $("#fcKpi").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; state.kpi = b.dataset.k; $$("#fcKpi button").forEach(x => x.classList.toggle("on", x === b)); forecast(); });
  $("#fcLegend").addEventListener("click", e => { const s = e.target.closest("[data-a]"); if (!s) return; const id = s.dataset.a; state.hidden.has(id) ? state.hidden.delete(id) : state.hidden.add(id); if (state.hidden.size >= adsOf(state.adset).length) state.hidden.delete(id); forecast(); });
  addEventListener("scroll", () => $("#nav").classList.toggle("scrolled", scrollY > 20), { passive: true });
  $("#theme").onclick = () => { const r = document.documentElement, dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches; r.dataset.theme = dark ? "light" : "dark"; renderAll(); };
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { forecast(); whatif(); proof(); }, 200); });
  heroCanvas();
  state.adset = brandSets()[0].id; state.studioAud = state.adset;
  document.documentElement.style.setProperty("--accent", BRAND[state.brand]);
  renderAll(); detectLive();
}
init();
})();
