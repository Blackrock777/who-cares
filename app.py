"""Campaign rehearsal: forecasts, audience evidence and bounded decision scenarios."""
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "out"
VERT = {"beauty_skincare": "Nuvola Derma Lab · skincare", "pet_ecommerce": "Coda Felice · pet supplies",
        "abbigliamento": "Filo Grigio · clothing"}
st.set_page_config(page_title="Who Cares · Campaign rehearsal", page_icon="◉", layout="wide")
st.title("Who Cares")
st.markdown("### Rehearse your campaign before you spend")
st.caption("Simulated Wevion challenge data · Forecast clicks and auction costs, compare creatives, and test budget scenarios.")


@st.cache_data
def load(snapshot):
    p = pd.read_csv(OUT / "predictions.csv", parse_dates=["data"])
    p["cpc_pred"] = p.cpm_pred / (10*p.ctr_pred)
    assets = pd.concat([pd.read_csv(f) for f in sorted((ROOT / "data/raw/asset_creativi").glob("*.csv"))])
    return (p, json.loads((OUT / "audiences.json").read_text()),
            json.loads((OUT / "decisions.json").read_text()), pd.read_csv(OUT / "validation.csv"),
            assets, json.loads((OUT / "run_manifest.json").read_text()))


required = ["predictions.csv", "audiences.json", "decisions.json", "validation.csv", "run_manifest.json"]
missing = [name for name in required if not (OUT / name).exists()]
if missing:
    st.error("Generate the campaign outputs first: " + ", ".join(missing))
    st.code("python src/pipeline.py", language="bash")
    st.stop()
p, audiences, decisions, validation, assets, manifest = load(tuple((OUT / n).stat().st_mtime_ns for n in required))
with st.sidebar:
    st.markdown("**Campaign workspace**")
    vertical = st.selectbox("Advertiser", list(VERT), format_func=VERT.get)
    segment = st.selectbox("Audience segment", sorted(p.loc[p.vertical == vertical, "adset_id"].unique()))
    st.caption(audiences[segment]["name"])
    st.divider()
    st.markdown("**What the numbers mean**")
    st.caption("CTR: clicks per 100 impressions. CPM: euro per 1,000 impressions. CPC: euro per click.")
    st.caption("Targeting and demographics are hidden. Behavioural profiles are hypotheses, not recovered identities.")

chosen = validation[(validation.model == "blend +index") & (validation.metric == "ctr")].iloc[0]
cols = st.columns(4)
cols[0].metric("Daily forecasts", len(p))
cols[1].metric("Audience segments", p.adset_id.nunique())
cols[2].metric("Held-out CTR error", f"{chosen.MAPE:.1f}%")
cols[3].metric("Held-out CTR winners", chosen.winners)
st.caption("Proof window: trained through 1 Nov, predicted 2-15 Nov. Winner accuracy is across 12 sets in this window; Black Friday outcomes are hidden.")
tab_compare, tab_audience, tab_budget, tab_lab, tab_proof = st.tabs(
    ["Compare ads", "Audience evidence", "Budget scenarios", "Creative lab", "Validation & exports"])

with tab_compare:
    st.subheader(f"Which creative should {segment} test first?")
    week = st.selectbox("Decision window", list(dict.fromkeys(x["week"] for x in decisions["creative"])))
    recs = pd.DataFrame(decisions["creative"])
    rec = recs[(recs.adset_id == segment) & (recs.week == week)].iloc[0]
    st.markdown(f"**First candidate: {rec['push']}** · predicted CTR **{rec['push_ctr']:.2f}%**")
    st.info(f"{rec['action']}. Candidates are compared on the same {rec['comparison_days']} days: "
            f"{rec['comparison_start']} to {rec['comparison_end']}.")
    asset = assets[assets.asset_id == rec["push_asset"]].iloc[0]
    st.markdown(f"**{asset.headline}**")
    st.caption(asset.descrizione_visual)
    sub = p[p.adset_id == segment]
    metric = st.radio("Show", ["ctr", "cpm", "cpc"], horizontal=True,
                      format_func=lambda x:{"ctr":"CTR %", "cpm":"CPM €", "cpc":"CPC €"}[x])
    base = alt.Chart(sub).encode(x=alt.X("data:T", title=None), color=alt.Color("ad_id:N", title="Ad"))
    line = base.mark_line(point=True).encode(y=alt.Y(f"{metric}_pred:Q", title={"ctr":"CTR %", "cpm":"CPM €", "cpc":"CPC €"}[metric]),
                                           tooltip=["data:T", "ad_id:N", alt.Tooltip(f"{metric}_pred:Q", format=".3f")])
    chart = line if metric == "cpc" else base.mark_area(opacity=.12).encode(y=f"{metric}_lo:Q", y2=f"{metric}_hi:Q") + line
    rule = alt.Chart(pd.DataFrame({"event":pd.to_datetime(["2026-11-27"])})).mark_rule(strokeDash=[4,4], color="#666").encode(x="event:T")
    _chart = (chart+rule).properties(height=310)
    try:
        st.altair_chart(_chart, width="stretch")
    except TypeError:  # Streamlit before the width= API
        st.altair_chart(_chart, use_container_width=True)
    st.caption("Shading: empirical daily 80% intervals; dashed line: Black Friday. CTR coverage was below 80% in the later validation week. "
               "The 2025 seasonal pattern is transferred to 2026; that transfer has not been tested on Black Friday outcomes.")
    dates = sub.data.between(rec["comparison_start"], rec["comparison_end"])
    ranking = sub[dates].groupby(["ad_id", "asset_id", "leva", "formato"]).agg(
        ctr_percent=("ctr_pred", "mean"), cpm_eur=("cpm_pred", "mean"), new_ad=("cold_start", "max")).reset_index().sort_values("ctr_percent", ascending=False)
    st.dataframe(ranking.round(3), hide_index=True, width="stretch")
    with st.expander("Why this forecast? What the model uses"):
        st.write("Creative descriptions are tagged for hooks, heavy text, people speaking, discounts and other features. "
                 "The model combines those with segment identity, days since launch, daily budget and calendar/market benchmarks. "
                 "These are predictive associations. The creative lab shows the model's sensitivity to individual tags.")
        st.caption("CPM reflects auction costs, not sales. Higher CTR does not establish conversion or revenue lift.")

with tab_audience:
    hyp = audiences[segment]
    st.subheader(hyp["name"])
    st.write(hyp["who"])
    st.caption(hyp["confidence"])
    for evidence in hyp["evidence"]:
        st.markdown(f"- {evidence}")
    st.markdown(f"**Alternative explanation:** {hyp['alternative']}")
    st.markdown(f"**Action to test:** {hyp['implication']}")
    st.info(hyp["demographics"])
    st.write("The forecaster models each ad set's response to creative and context. Viewer scenarios in the creative lab "
             "illustrate possible people behind that response; they do not identify real ages or habits.")

with tab_budget:
    st.subheader("Where could the same budget buy more clicks?")
    st.caption(decisions["assumptions"])
    b = pd.DataFrame(decisions["budget"])
    b = b[b.campaign_id == p.loc[p.vertical == vertical, "campaign_id"].iloc[0]]
    st.dataframe(b[["adset_id", "budget", "budget_proposed", "cpc", "clicks_per_day", "clicks_per_day_proposed"]].round(2),
                 hide_index=True, width="stretch")
    summary = b.iloc[0]
    c1,c2,c3 = st.columns(3)
    c1.metric("Scenario extra clicks / day", f"{summary.campaign_gain_clicks_per_day:+.1f}")
    c2.metric("Elasticity sensitivity", f"{summary.gain_elasticity_min:+.1f} to {summary.gain_elasticity_max:+.1f}")
    c3.metric("Adverse KPI sensitivity", f"{summary.gain_adverse_kpi_min:+.1f}")
    st.warning("Treat this as a small allocation test. Future delivery shares and the causal budget response are unknown. "
               "The adverse scenario can lose clicks; none of these gains is a sales forecast.")
    st.caption("The table averages the daily plan. Every campaign/day preserves its exact budget, with each ad set limited to ±20%. "
               "Elasticity 0.42 is a scenario assumption, with 0.25-1.0 sensitivity. The uncertainty figures are scenarios, not probability bounds.")
    st.download_button("Download daily budget plan", (OUT / "decisions_budget_daily.csv").read_bytes(), "budget_scenarios_daily.csv", "text/csv")

with tab_lab:
    st.subheader("Try a creative before launch")
    st.caption("Describe the creative in Italian, as in the kit. New descriptions are predictions outside the training catalogue.")
    with st.form("new"):
        c1,c2,c3 = st.columns(3)
        new_vertical = c1.selectbox("Creative advertiser", list(VERT), format_func=VERT.get)
        lever = c2.selectbox("Lever", ["black_friday", "urgency", "scarcity"])
        formato = c3.selectbox("Format", ["video", "immagine", "carosello"])
        c1,c2,c3 = st.columns(3)
        duration = c1.number_input("Video length (seconds)", 1, 60, 14)
        cta = c2.selectbox("Call to action", ["Acquista ora", "Scopri di più"])
        launch = c3.date_input("Launch date", pd.Timestamp("2026-11-23"), min_value=pd.Timestamp("2026-11-16"), max_value=pd.Timestamp("2026-11-30"))
        headline = st.text_input("Headline", "Black Friday: -40% solo oggi")
        text = st.text_input("Primary text", "Tutta la linea a -40% fino a mezzanotte.")
        description = st.text_area("Visual description", "Creator in bagno parla in camera, apre con '-40% SOLO OGGI' nei primi 2 secondi, ritmo veloce.")
        submitted = st.form_submit_button("Predict audience response")
    if submitted:
        from score_new import score
        try:
            with st.spinner("Scoring the creative across four audiences…"):
                st.session_state["creative_result"] = (*score(new_vertical, lever, formato, duration, headline, text, cta, description, str(launch)), new_vertical)
        except ValueError as exc:
            st.session_state.pop("creative_result", None)
            st.error(str(exc))
    if "creative_result" in st.session_state:
        per_set, tags, deltas, daily, result_vertical = st.session_state["creative_result"]
        st.markdown("**Expected response by audience segment**")
        st.dataframe(per_set, width="stretch")
        st.caption("Bounds shown here are averages of daily bounds, not 80% intervals for the window average. CPC assumes equal daily spend.")
        explain_set = st.selectbox("Explain response for", list(per_set.index))
        with st.expander("Creative tags and model sensitivities", expanded=True):
            st.dataframe(tags.rename("present").to_frame().T, hide_index=True, width="stretch")
            st.dataframe(deltas[deltas.adset_id == explain_set].drop(columns="adset_id"), hide_index=True, width="stretch")
            st.caption("Feature changes are model sensitivities, not causal effects. Unseen feature combinations may be unreliable. "
                       "Related tags are changed together where needed for consistency.")
        st.markdown("**Synthetic viewer scenario**")
        st.caption("Ages, needs and habits below are illustrative assumptions. Age has no learned effect. "
                   "The panel is calibrated so its weighted expected CTR equals the statistical forecast.")
        strength = st.slider("Assumed habit differences (0 = no unmeasured differences)", 0., 2., 0., .1)
        c1,c2,c3 = st.columns(3)
        age_mix = [c1.number_input("18-34 age weight", 0, 100, 34), c2.number_input("35-54 age weight", 0, 100, 33),
                   c3.number_input("55-70 age weight", 0, 100, 33)]
        from simulation import simulate
        try:
            panel, sim = simulate(float(per_set.loc[explain_set, "ctr"]), result_vertical, tags,
                                  strength=strength, age_weights=age_mix)
            st.dataframe(panel.round(3), hide_index=True, width="stretch")
            st.caption(f"10,000 illustrative viewers: {sim['expected_clicks']:.1f} expected clicks; "
                       f"{sim['sampled_clicks']} sampled with seed {sim['seed']}. Sampling is not accuracy evidence. "
                       "Subgroup rates are scenarios, not validated demographic predictions.")
        except ValueError as exc:
            st.error(str(exc))

with tab_proof:
    st.subheader("What has actually been tested?")
    st.write("Official validation: train through 1 November, predict 2-15 November. Models never train on validation outcomes. "
             "Earlier rolling windows compare model stability. Final Black Friday accuracy is unknown.")
    st.dataframe(validation, hide_index=True, width="stretch")
    st.caption("MAE is percentage points for CTR and euro for CPM. MAPE is mean absolute percentage error. "
               "Global Spearman ranks ads across all audiences; within-set Spearman is more relevant to creative choice. "
               "Winners use unweighted per-ad daily means, as in the original implementation.")
    cov = validation[validation.model.str.contains("9-15 Nov")][["metric", "coverage80"]]
    st.markdown("**Interval coverage checked on 9-15 Nov, after calibration on 2-8 Nov**")
    st.dataframe(cov, hide_index=True)
    st.warning("Suspected quality issues were excluded from training and the primary validation. Their causes are unconfirmed. "
               "The breakdown includes every supplied validation outcome; MAE and WAPE include the zero-click row. MAPE cannot include zero CTR.")
    for title, filename in [("Earlier rolling validation", "rolling_validation.csv"), ("Validation breakdown", "validation_breakdown.csv"),
                            ("Flagged source rows", "quality_flags.csv")]:
        if (OUT / filename).exists():
            with st.expander(title):
                st.dataframe(pd.read_csv(OUT / filename), hide_index=True, width="stretch")
    with st.expander("Reproducibility and output checks"):
        st.json(manifest)
    st.download_button("Download all required predictions", (OUT / "predictions.csv").read_bytes(), "predictions.csv", "text/csv")
    st.download_button("Download held-out predictions", (OUT / "validation_predictions.csv").read_bytes(), "validation_predictions.csv", "text/csv")
