"""Wevion BigHack 2026: the campaign tool. Run with:  ./.venv/bin/streamlit run app.py"""
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "out"

st.set_page_config(page_title="Clienti che non esistono", layout="wide")
st.title("Clienti che non esistono")
st.caption("Immagina il pubblico, prevedi CTR e CPM, decidi dove mettere il budget. "
           "Audiences inferred from behaviour, Black Week forecasts with error bands, and a budget plan.")


@st.cache_data
def load():
    p = pd.read_csv(OUT / "predictions.csv", parse_dates=["data"])
    p["cpc_pred"] = p["cpm_pred"] / (10 * p["ctr_pred"])
    aud = json.load(open(OUT / "audiences.json"))
    fp = pd.read_csv(OUT / "adset_fingerprint.csv", index_col=0)
    dec = json.load(open(OUT / "decisions.json"))
    val = pd.read_csv(OUT / "validation.csv")
    assets = pd.concat([pd.read_csv(f) for f in (ROOT / "data/raw/asset_creativi").glob("*.csv")])
    return p, aud, fp, dec, val, assets


p, aud, fp, dec, val, assets = load()
VERT = {"beauty_skincare": "Nuvola Derma Lab (beauty & skincare)",
        "pet_ecommerce": "Coda Felice (pet e-commerce)",
        "abbigliamento": "Filo Grigio (abbigliamento)"}

tab_aud, tab_pred, tab_dec, tab_new, tab_val = st.tabs(
    ["1 · Pubblici", "2 · Previsioni 16-30 Nov", "3 · Decisioni", "4 · Nuova creatività", "Validazione"])

with tab_aud:
    st.subheader("Who is behind each ad set, inferred from the numbers")
    st.dataframe(fp.style.format(precision=3), width='stretch')
    for rank in "1234":
        hyp = aud[f"NDL-AS{rank}"]
        sets = ", ".join(k for k in aud if k.endswith(rank))
        with st.expander(f"Ad set {rank} ({sets}): {hyp['name']}", expanded=(rank == "4")):
            st.markdown(f"**Who:** {hyp['who']}")
            st.markdown("**Evidence:**\n" + "\n".join(f"- {e}" for e in hyp["evidence"]))
            st.markdown(f"**Plan:** {hyp['implication']}")

with tab_pred:
    vert = st.selectbox("Advertiser", list(VERT), format_func=VERT.get)
    metric = st.radio("KPI", ["ctr", "cpm", "cpc"], horizontal=True,
                      format_func=lambda m: {"ctr": "CTR %", "cpm": "CPM €", "cpc": "CPC €"}[m])
    sub = p[p["vertical"] == vert]
    for adset, grp in sub.groupby("adset_id"):
        st.markdown(f"**{adset} · {aud[adset]['name']}**")
        base = alt.Chart(grp).encode(x=alt.X("data:T", title=None), color=alt.Color("ad_id:N", title="Ad"))
        line = base.mark_line().encode(y=alt.Y(f"{metric}_pred:Q", title=metric.upper()))
        chart = line
        if metric != "cpc":
            band = base.mark_area(opacity=0.15).encode(y=f"{metric}_lo:Q", y2=f"{metric}_hi:Q")
            chart = band + line
        rule = alt.Chart(pd.DataFrame({"d": ["2026-11-27"]})).mark_rule(strokeDash=[4, 4]).encode(x="d:T")
        st.altair_chart((chart + rule).properties(height=220), use_container_width=True)
    st.markdown("**Per-ad averages over the window (80% bands)**")
    summ = pd.read_csv(OUT / "summary_by_ad.csv")
    st.dataframe(summ[summ["vertical"] == vert].drop(columns=["vertical"]), width='stretch', hide_index=True)

with tab_dec:
    st.subheader("Budget: where a euro buys the most clicks")
    st.caption("Cost per click = CPM / (10 × CTR). Clicks scale with budget^0.42, measured in the history "
               "when an ad set doubled its budget (CPM +28%, CTR −14%).")
    b = pd.DataFrame(dec["budget"])
    st.dataframe(b[["campaign_id", "adset_id", "budget", "ctr", "cpm", "cpc", "clicks_per_day",
                    "budget_proposed", "clicks_per_day_proposed", "note"]].round(2),
                 width='stretch', hide_index=True)
    st.subheader("Creative and lever: push and pause, per ad set and week")
    c = pd.DataFrame(dec["creative"])
    st.dataframe(c[["adset_id", "week", "push", "push_leva", "push_formato", "push_ctr", "push_band",
                    "pause", "pause_ctr", "ctr_gap", "confident"]], width='stretch', hide_index=True)
    st.subheader("Timing: the market day by day")
    t = pd.DataFrame(dec["timing"])
    st.line_chart(t.set_index("data")[["cpm", "ctr"]])

with tab_new:
    st.subheader("Score a creative before it exists")
    st.caption("Describe the creative the way the kit does. The model tags it, predicts CTR and CPM per ad set "
               "for the Black Week window, and shows which features move the prediction.")
    with st.form("new"):
        c1, c2, c3 = st.columns(3)
        vert = c1.selectbox("Vertical", list(VERT), format_func=VERT.get)
        leva = c2.selectbox("Lever", ["black_friday", "urgency", "scarcity"])
        formato = c3.selectbox("Format", ["video", "immagine", "carosello"])
        c4, c5, c6 = st.columns(3)
        durata = c4.number_input("Video length (s)", 0, 60, 14)
        cta = c5.selectbox("CTA", ["Acquista ora", "Scopri di più"])
        launch = c6.date_input("Launch date", pd.Timestamp("2026-11-23"), min_value=pd.Timestamp("2026-11-16"), max_value=pd.Timestamp("2026-11-30"))
        headline = st.text_input("Headline", "Black Friday: -40% solo oggi")
        testo = st.text_input("Primary text", "Tutta la linea a -40% fino a mezzanotte.")
        desc = st.text_area("Visual description (Italian, like the kit)",
                            "Creator in bagno parla in camera, apre con '-40% SOLO OGGI' nei primi 2 secondi, ritmo veloce.")
        go = st.form_submit_button("Predict")
    if go:
        from score_new import score
        per_set, tags, deltas, daily = score(vert, leva, formato, durata, headline, testo, cta, desc, str(launch))
        per_set.index = [f"{i} · {aud[i]['name']}" for i in per_set.index]
        st.markdown("**Predicted per ad set, averaged over the window (80% bands)**")
        st.dataframe(per_set, width='stretch')
        c1, c2 = st.columns(2)
        c1.markdown("**Features the model found**")
        c1.dataframe(tags.rename("present").to_frame(), width='stretch')
        c2.markdown("**Why: CTR change if the feature were flipped**")
        c2.dataframe(deltas, width='stretch', hide_index=True)
        st.line_chart(daily[["ctr_pred", "ctr_lo", "ctr_hi"]])

with tab_val:
    st.subheader("Validation: trained to 1 Nov, scored on 2-15 Nov (12 cold-start ads)")
    st.dataframe(val, width='stretch', hide_index=True)
    st.markdown("Bands were calibrated on 2-8 Nov and checked on 9-15 Nov: 71% coverage on CTR, 83% on CPM, "
                "against an 80% target.")
