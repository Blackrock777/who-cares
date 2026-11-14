# Who Cares · Campaign rehearsal

Forecast an ad before launch, compare its response across 12 audience segments, and test where the same budget could buy more clicks. Built for Wevion BigHack 2026, “Clienti che non esistono”.

All advertisers, creative descriptions and outcomes in the organisers' kit are **simulated**. The forecast window is 16–30 November 2026. No external advertising outcomes or persona datasets are used.

## Run

Tested with Python 3.12.14. Use Python 3.12 and the pinned dependencies; the system Python on the development machine is a different version.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python src/pipeline.py
.venv/bin/python -m streamlit run app.py
```

The application opens at http://localhost:8501. Existing generated outputs are included. `pipeline.py` rebuilds the forecasts, validations, audience evidence and decisions from `data/raw`. It archives the initially supplied prediction, validation, audience and decision files under `out/audit/` before replacing them. Raw kit files are never changed. The local `out/model.pkl` is intentionally excluded from Git; the creative lab builds it automatically if absent or stale.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Individual commands remain available: `python src/model.py rolling`, `python src/model.py validate`, `python src/model.py predict`, `python src/audiences.py`, `python src/decide.py`. Run the full pipeline after source/data changes to keep the dashboard outputs consistent.

## What to demonstrate

1. **Compare ads:** select an advertiser and audience. See the first creative to test, its copy, CTR/CPM/CPC forecasts, daily intervals and a ranking on common dates.
2. **Audience evidence:** measured response, exposure, fatigue, alternative explanations and confidence for each segment.
3. **Budget scenarios:** daily allocation that preserves campaign budgets, limits changes to 20%, and shows sensitivity to uncertain returns.
4. **Creative lab:** score a new Italian creative description across four audience segments, inspect tag sensitivities, and explore a synthetic viewer panel.
5. **Validation & exports:** compare against the baseline, inspect weak segments, see quality exclusions and download all required forecasts.

## Measured performance

Training: 1,426 cleaned ad-days through 1 November. Evaluation: 443 cleaned ad-days on 2–15 November. Twelve ads are unseen at training time. Full supplied validation contains 444 rows; the additional row has zero CTR and is also reported using MAE/WAPE.

| Model | CTR MAE, percentage points | CTR MAPE | CTR global / within-set Spearman | CTR winners | CPM MAPE |
|---|---:|---:|---:|---:|---:|
| Last 7 days per ad; ad-set fallback | 0.316 | 33.3% | 0.65 / 0.21 | 4/12 | 8.6% |
| Previous: tree/ridge blend for both KPIs | 0.228 | 25.6% | 0.85 / 0.66 | 11/12 | 7.2% |
| **Production: same CTR model; CPM budget/season ensemble** | 0.228 | 25.6% | 0.85 / 0.66 | 11/12 | **6.3%** |

CPM detail on the same window: MAE €0.755 → €0.641, mean log bias −3.4% → −0.2%, new-ad log error 0.112 → 0.067. Across three earlier windows plus this one the CPM model is better in all four (mean MAPE 7.5% → 6.6%); a bootstrap over ads gives a 95% interval for the log-error change that excludes zero. CTR was tested against eight alternatives (hierarchical ridge, Poisson rate model, recency weighting, impression weighting, seasonal-naive hybrids): none beat the existing blend beyond noise, so CTR is unchanged. Daily CTR carries roughly 13% irreducible click-count noise at these volumes.

The original point metrics were independently reproduced. CTR forecasts are unchanged from the first submission; CPM forecasts changed (see `src/cpm.py` and AUDIT.md section I) and the earlier file is kept at `out/audit/pre_cpm_audit_predictions.csv`. Ridge alone has better CTR MAPE on this particular window (24.0%), while the index-adjusted tree has better CPM MAPE (6.8%). Three earlier 14-day windows favour the blend overall among the learned candidates; see `out/rolling_validation.csv`. Those checks use only completed monthly market observations at each forecast cutoff. The simple baseline remains competitive, particularly for CPM. The known November window has been examined during development; it is not a pristine final test. The 699 hidden-outcome rows are the actual competition test.

**Intervals are empirical, not a guarantee.** With the production models, bands calibrated on 2–8 November covered 71% (CTR) and 80% (CPM) of 9–15 November. Calibration on 2–8 November contains no new ads. The original fallback was an arbitrary 0.4 log-width; the revised method uses new-ad errors from an earlier temporal holdout instead. Coverage on 9–15 November remains below the 80% target: see `out/interval_validation.json` for exact aggregate and known/new-ad coverage. Average daily bounds shown in summaries are not confidence intervals for a window average or a winning probability.

## How forecasts work

`src/features.py` joins each ad/date to creative descriptions, launch dates, planned daily budgets and the supplied calendar. Keyword rules extract hooks, speaking to camera, heavy text, late discounts, timers, people, studio backgrounds, prices and reviews. Format, duration, headline discount and text length are included. These rules read the supplied descriptions; no image or video was supplied.

**CTR.** `src/model.py` fits a gradient-boosted tree and a regularized ridge model to log CTR and log CPM after subtracting the log 2025 weekly market index. It averages the two predictions in log space, then restores the seasonal index. Both models use training-only preprocessing. Market indices remain predictors as well, so detrending does not force a fixed causal seasonal effect. The supplied 2025 shape is a transfer assumption, not measured Black Friday 2026 accuracy.

**CPM.** `src/cpm.py` replaces the blend for CPM, for three measured reasons. (1) Seven of twelve ad sets get Black Week budgets 1.25–2.5× their starting budget, while history contains one budget change (NDL ad set 4, €45→€90 for one week). The boosted tree returned no budget response at all on the forecast rows, so the blend applied about half of what the one observed event implies. The budget effect is now one constant elasticity (CPM ∝ budget_ratio^0.31, estimated with ad effects and fatigue controlled) applied to every learner. (2) The ridge had learned a negative coefficient on the seasonal features that cancelled 12% of the Black Friday index on the forecast rows; in validation that variant under-predicted by 5% as soon as the index rose. The CPM learners now see no seasonal feature: season enters only by multiplying the index back. (3) The 2025 weekly index is noisy week to week and 2026 CPM does not repeat that noise (same-ad weekly changes follow it with slope 0.21 ± 0.07, while the trend is followed one-for-one), so the CPM index is averaged across the three verticals and fitted with a rise-to-peak, fall-after curve; the Black Friday peak value is kept. The CPM forecast is the mean of a hierarchical ridge, boosted trees and the ad's own last-7-day level, each on the budget-neutral, de-seasonalised target. New ads use the first two. **Assumptions that cannot be validated before the hidden results:** the elasticity comes from one event in one warm ad set and is extrapolated to 2.5×; the 2025 Black Friday shape transfers to 2026.

A 364-day offset aligns weekdays and the Black Friday/Cyber Monday weeks correctly. November market CPM is projected from October 2026 using the 2025 November/October ratio. A model's forecast context restricts monthly observations to completed months at its training cutoff. Future budgets are known inputs supplied by the organisers.

Ten suspected quality anomalies are excluded from training: eight pet zero-click rows, one clothing spend spike, and one skincare zero-click row. Their causes are **unconfirmed**. All exclusions are exported in `out/quality_flags.csv`; validation sensitivity includes the supplied zero-click outcome rather than hiding it. MAPE excludes undefined zero denominators; MAE and WAPE include them.

## What the audience simulation means

Behavioural profiles are hypotheses generated from each segment's measured fingerprint; no profile is assigned from the numeric ad-set ID. High frequency and high CTR are consistent with warm audiences, not proof of retargeting. The code permits ambiguous profiles instead of forcing four audience types in every advertiser. Within-ad fatigue and same-asset/day comparisons reduce some creative/date mixing, without establishing causality.

Age, gender, income, targeting configuration and browsing habits are **not observed**. The creative lab's viewer panel introduces explicit age, habit and need assumptions. It calibrates individual click probabilities so their population-weighted expected CTR equals the segment forecast. Age has no learned effect. Optional habit sensitivity is a user-defined scenario and defaults to zero. Simulated click counts are illustrative random draws, never validation evidence or demographic predictions.

## What budget recommendations mean

CPC = CPM / (10 × CTR%) for a single ad/day. A segment's click efficiency is the average of each active ad's `10 × CTR / CPM`, assuming equal spend across active ads. Actual future platform delivery shares are unknown.

Daily allocation maximizes expected clicks under the scenario `clicks(B) = baseline_clicks × (B / baseline_budget)^0.42`. Every campaign/day retains its total budget, each segment stays within ±20%, and euro-cent rounding preserves totals. The 0.42 elasticity is **an assumption**, not a fitted causal effect. Sensitivity covers elasticity 0.25–1.0 and adverse KPI bounds. Recommendations can lose clicks under adverse assumptions. They are tests to consider, not guaranteed gains or sales predictions.

Creative recommendations compare candidates on dates when all are active. Overlapping daily uncertainty leads to “test challenger”, rather than an unconditional pause recommendation. Feature toggles in the creative lab describe model sensitivity, not the effect a real edit will cause.

## Deliverables and evidence

| File | Purpose |
|---|---|
| `out/predictions.csv` | All 699 required ad-days, CTR/CPM point forecasts, daily bounds and cold-start flags |
| `out/run_manifest.json` | Input/code fingerprint, versions, training/calibration dates and output checks |
| `out/validation.csv`, `out/validation_predictions.csv` | Reproducible held-out metrics and row-level predictions |
| `out/validation_breakdown.csv`, `out/rolling_validation.csv` | Advertiser, segment, date, cold-start and earlier-window checks |
| `out/interval_validation.json` | Interval provenance and empirical coverage |
| `out/audiences.md`, `out/audiences.json` | Twelve audience hypotheses and measured evidence |
| `out/decisions_budget_daily.csv` | Daily, bounded, budget-conserving scenarios |
| `out/seasonality_assumptions.csv` | Forecast-date alignment to 2025 market weeks |
| `AUDIT.md` | Independent review of the initial project, verified results, fixes and remaining risks |
| `DESIGN.md` | System architecture, assumptions and mathematical contracts |
| `DEMO.md` | Three-minute recording script and submission copy |

**Submission still requires a recorded video link.** The repository includes a script, not a recording. Submit through the event platform yourself after checking the repository/video links and team details; no project has been published or submitted by this code.

Tools: Python, pandas, NumPy, scikit-learn, SciPy, Streamlit and Altair. Claude assisted the initial implementation and the final ML audit (CPM model); Codex assisted the independent audit and subsequent changes. No LLM-generated person-level response is presented as measured evidence.
