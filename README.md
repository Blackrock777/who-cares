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
| Tree/ridge blend with 2025 index | 0.228 | 25.6% | 0.85 / 0.66 | 11/12 | 7.2% |

These original point metrics were independently reproduced. The regenerated point forecasts are unchanged. Ridge alone has better CTR MAPE on this particular window (24.0%), while the index-adjusted tree has better CPM MAPE (6.8%). Three earlier 14-day windows favour the blend overall among the learned candidates; see `out/rolling_validation.csv`. Those checks use only completed monthly market observations at each forecast cutoff. The simple baseline remains competitive, particularly for CPM. The known November window has been examined during development; it is not a pristine final test. The 699 hidden-outcome rows are the actual competition test.

**Intervals are empirical, not a guarantee.** Calibration on 2–8 November contains no new ads. The original fallback was an arbitrary 0.4 log-width; the revised method uses new-ad errors from an earlier temporal holdout instead. Coverage on 9–15 November remains below the 80% target: see `out/interval_validation.json` for exact aggregate and known/new-ad coverage. Average daily bounds shown in summaries are not confidence intervals for a window average or a winning probability.

## How forecasts work

`src/features.py` joins each ad/date to creative descriptions, launch dates, planned daily budgets and the supplied calendar. Keyword rules extract hooks, speaking to camera, heavy text, late discounts, timers, people, studio backgrounds, prices and reviews. Format, duration, headline discount and text length are included. These rules read the supplied descriptions; no image or video was supplied.

`src/model.py` fits a gradient-boosted tree and a regularized ridge model to log CTR and log CPM after subtracting the log 2025 weekly market index. It averages the two predictions in log space, then restores the seasonal index. Both models use training-only preprocessing. Market indices remain predictors as well, so detrending does not force a fixed causal seasonal effect. The supplied 2025 shape is a transfer assumption, not measured Black Friday 2026 accuracy.

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

Tools: Python, pandas, NumPy, scikit-learn, SciPy, Streamlit and Altair. Claude assisted the initial implementation; Codex assisted the independent audit and subsequent changes. No LLM-generated person-level response is presented as measured evidence.
