/* Who Cares v2: one screen, three questions. Everything else lives in dettagli.html.
   Rule for every element: if it disappeared, would anyone notice? Only what changes a decision stays. */
(() => {
const D = window.DATA, $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
let LANG = store.get("lang") || "it";
const BRAND = { NDL: "#c4694f", CDF: "#6c8a5f", FGR: "#3f6e8c" };

const T = {
  it: {
    q: "Chi vedrà la campagna, cosa mostrargli, quanto spendere.",
    chi: "Chi?", cosa: "Cosa?", quanto: "Quanto?", try: "Mostralo a 1.000 persone simulate", why: "Perché questi numeri? Il metodo, le prove, le fonti →",
    names: { broad: "Pubblico ampio", deal: "Sensibili alle offerte", uncertain: "Interessi misti", warm: "Clienti che tornano", selective: "Pubblico selettivo" },
    women: "Soprattutto donne", men: "Soprattutto uomini", mixed: "Donne e uomini", age: "{a}–{b} anni",
    cheap: "costano poco", dear: "costano di più", avgcost: "costano nella media",
    lowclick: "cliccano meno della media", highclick: "cliccano più della media", avgclick: "cliccano nella media",
    warm: "Ti conoscono già: rivedono l'annuncio e cliccano {x} volte la media.",
    ctr: "{v}% clicca", runner: "Alternativa: {c} ({v}%).", same: "Vince per tutti i pubblici di questo brand: un solo messaggio basta.",
    diff: "Per questo pubblico vince un messaggio diverso.",
    more: "€{b} al giorno", up: "Spendi di più qui: da €{from} a €{to} al giorno. Qui ogni euro porta più clic che altrove.",
    down: "Spendi meno qui: da €{from} a €{to} al giorno. Quei soldi rendono di più su un altro pubblico.",
    keep: "Tieni €{to} al giorno.", gain: "Stesso budget totale, +{g} clic al giorno per la campagna.",
    when: "Il giorno più conveniente della Black Week: {d}.", clicked: "{k} su 1.000 hanno cliccato.",
    lever: { scarcity: "scarsità", urgency: "urgenza", black_friday: "Black Friday" }, fmt: { immagine: "immagine", video: "video", carosello: "carosello" },
  },
  en: {
    q: "Who will see the campaign, what to show them, how much to spend.",
    chi: "Who?", cosa: "What?", quanto: "How much?", try: "Show it to 1,000 simulated people", why: "Why these numbers? The method, the proof, the sources →",
    names: { broad: "Broad reach", deal: "Deal-responsive", uncertain: "Mixed interests", warm: "Returning customers", selective: "Selective buyers" },
    women: "Mostly women", men: "Mostly men", mixed: "Women and men", age: "aged {a}–{b}",
    cheap: "they're cheap to reach", dear: "they cost more", avgcost: "they cost about average",
    lowclick: "click less than average", highclick: "click more than average", avgclick: "click about average",
    warm: "They already know you: they see the ad again and click {x}× the average.",
    ctr: "{v}% click", runner: "Runner-up: {c} ({v}%).", same: "It wins for every audience of this brand: one message is enough.",
    diff: "A different message wins for this audience.",
    more: "€{b} a day", up: "Spend more here: from €{from} to €{to} a day. Each euro buys more clicks here than elsewhere.",
    down: "Spend less here: from €{from} to €{to} a day. That money works harder on another audience.",
    keep: "Keep €{to} a day.", gain: "Same total budget, +{g} clicks a day for the campaign.",
    when: "Cheapest day of Black Week: {d}.", clicked: "{k} of 1,000 clicked.",
    lever: { scarcity: "scarcity", urgency: "urgency", black_friday: "Black Friday" }, fmt: { immagine: "image", video: "video", carosello: "carousel" },
  },
};
const t = (k, v = {}) => { let s = k.split(".").reduce((o, x) => o && o[x], T[LANG]) ?? k; for (const x in v) s = s.split("{" + x + "}").join(v[x]); return s; };
const num = (x, n = 0) => Number(x).toLocaleString(LANG === "it" ? "it-IT" : "en-GB", { minimumFractionDigits: n, maximumFractionDigits: n });
const cap = s => s[0].toUpperCase() + s.slice(1);

let brand = "NDL", aud = null, people = [];
const sets = () => D.adsets.filter(s => s.advertiser === brand);

function sentence(s) {
  const P = s.population, o = P.observed, f = P.share_female.mean, a = P.mean_age.mean;
  const lo = Math.floor(Math.max(18, Math.round(a - 9)) / 5) * 5;
  const demo = `${f >= 0.65 ? t("women") : f <= 0.35 ? t("men") : t("mixed")}, ${t("age", { a: lo, b: lo + 15 })}.`;
  if (P.p_warm >= 0.7) return `${demo} ${t("warm", { x: num(o.ctr_vs_advertiser, 1) })}`;
  const cost = o.cpm_vs_advertiser < 0.92 ? t("cheap") : o.cpm_vs_advertiser > 1.08 ? t("dear") : t("avgcost");
  const click = o.ctr_vs_advertiser < 0.92 ? t("lowclick") : o.ctr_vs_advertiser > 1.08 ? t("highclick") : t("avgclick");
  return `${demo} ${cap(cost)} ${LANG === "it" ? "e" : "and"} ${click}.`;
}

function crowdOf(s, n) {
  let seed = 7; const r = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const cells = D.priors.cells, w = cells.map(c => s.population.cells[c].share), eff = D.priors.cell_effects.ctr.log_mult;
  const z = w.reduce((a, x, i) => a + x * Math.exp(eff[cells[i]]), 0), cum = []; w.reduce((a, x, i) => (cum[i] = a + x), 0);
  return Array.from({ length: n }, () => { const u = r() * cum[cum.length - 1]; let k = cum.findIndex(x => x >= u); if (k < 0) k = cells.length - 1;
    const [g, band] = cells[k].split("|"); const age = band === "55+" ? 55 + r() * 20 : +band.split("-")[0] + r() * 10;
    return { g, age, rel: Math.exp(eff[cells[k]]) / z }; });
}
const colour = p => `color-mix(in srgb, var(${p.g === "F" ? "--women" : "--men"}) ${Math.round(40 + 60 * Math.min(1, (p.age - 18) / 56))}%, var(--paper))`;

function render() {
  document.documentElement.lang = LANG;
  document.documentElement.style.setProperty("--accent", BRAND[brand]);
  $$("#lang button").forEach(b => b.classList.toggle("on", b.dataset.l === LANG));
  $$("[data-t]").forEach(e => (e.textContent = t(e.dataset.t)));
  $("#q").textContent = t("q"); $("#try").textContent = t("try"); $("#why").textContent = t("why");
  $("#brands").innerHTML = D.advertisers.map(a => `<button data-b="${a.id}" class="${a.id === brand ? "on" : ""}"><i style="background:${BRAND[a.id]}"></i>${a.name}</button>`).join("");
  if (!aud || !aud.startsWith(brand)) aud = sets()[0].id;
  $("#targets").innerHTML = sets().map(s => `<button data-a="${s.id}" class="${s.id === aud ? "on" : ""}">${t("names." + s.fingerprint.profile)}</button>`).join("");
  const s = D.adsets.find(x => x.id === aud);

  // Chi?
  $("#chiSay").textContent = sentence(s);
  people = crowdOf(s, 1000);
  $("#people").innerHTML = people.map(p => `<i style="background:${colour(p)}"></i>`).join("");
  $("#crowdOut").textContent = "";

  // Cosa? the creative forecast best for this audience as a new ad from 16 Nov
  const lab = D.lab.filter(x => x.audience === aud).sort((a, b) => b.ctr - a.ctr), win = lab[0], alt = lab[1];
  const c = D.creatives.find(x => x.id === win.creative);
  const winners = new Set(sets().map(x => D.lab.filter(y => y.audience === x.id).sort((a, b) => b.ctr - a.ctr)[0].creative));
  $("#ad").innerHTML = `<span class="tag">${t("lever." + c.lever)} · ${t("fmt." + c.format)}</span><b>${c.headline}</b><span>${c.body}</span>`;
  $("#ctr").textContent = t("ctr", { v: num(win.ctr, 2) });
  $("#cosaSay").textContent = `${winners.size === 1 ? t("same") : t("diff")} ${t("runner", { c: alt.creative.split("-")[1], v: num(alt.ctr, 2) })}`;

  // Quanto? the budget move for this audience (campaign total fixed) and the cheapest day
  const b = D.decisions.budget.find(x => x.adset_id === aud), d = b.budget_proposed - b.budget;
  $("#budget").textContent = t("more", { b: num(b.budget_proposed) });
  $("#quantoSay").textContent = `${Math.abs(d) < 1 ? t("keep", { to: num(b.budget_proposed) }) : t(d > 0 ? "up" : "down", { from: num(b.budget), to: num(b.budget_proposed) })} ${t("gain", { g: num(b.campaign_gain_clicks_per_day, 1) })}`;
  const tm = D.decisions.timing.slice().sort((a, b) => a.cpc - b.cpc)[0];
  $("#when").textContent = t("when", { d: new Date(tm.data + "T00:00:00").toLocaleDateString(LANG === "it" ? "it-IT" : "en-GB", { weekday: "long", day: "numeric", month: "long" }) });
  $("#try").onclick = () => watch(win.ctr);
}

function watch(ctr) {
  const dots = $("#people").children; let k = 0, r = Math.random;
  [...dots].forEach(d => d.classList.remove("hit", "dim"));
  people.forEach((p, i) => { const hit = r() < ctr / 100 * p.rel; if (hit) k++;
    setTimeout(() => dots[i].classList.add(hit ? "hit" : "dim"), i * 0.9); });
  setTimeout(() => ($("#crowdOut").textContent = t("clicked", { k })), 950);
}

$("#brands").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { brand = b.dataset.b; render(); } });
$("#targets").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { aud = b.dataset.a; render(); } });
$("#lang").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { LANG = b.dataset.l; store.set("lang", LANG); render(); } });
render();
})();
