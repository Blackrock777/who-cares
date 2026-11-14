# Independent technical audit · Wevion BigHack 2026

Audit date: 14 November 2026. Initial revision: `02678af`. This report separates the original implementation, executed findings, changes made after the user's approval, and remaining limitations. It does not estimate the probability of winning.

The project was first inspected read-only. The user then explicitly requested all three outcomes: audit, design and implementation. Existing outputs were archived before regeneration. The organisers' CSVs remain byte-identical to all 13 entries in the supplied ZIP.

## A. Executive verdict

The original project was a functioning small-data advertising forecaster with a Streamlit interface. It genuinely trained gradient-boosted trees and ridge models, used a prior-year market index, generated all 699 predictions and outperformed its stated naive baseline on the official validation window. Its reported point metrics were reproducible, and regenerating its prediction file produced identical numeric values.

Its explanation was stronger than its evidence. The four audience identities were hardcoded from the last character of the ad-set ID. Ages, incomes, Instagram habits and retargeting settings were not inferred. The budget curve was an assumed exponent justified by a single confounded episode. The nominal interval claim understated undercoverage and hid a fixed-width cold-start fallback. The new-creative demo crashed in a fresh checkout because the ignored model file was missing.

The revised project fixes the fresh-checkout failure, adds traceable audience hypotheses and explicitly hypothetical viewer simulation, validates outputs, improves allocation mathematics and exposes temporal/subgroup weaknesses. **Point forecasts have deliberately not changed.** No tested replacement consistently justified changing the production learner.

The tool is now executable and more defensible. **The complete competition submission is not ready until a video has been recorded and its link checked.** Forecast accuracy on the hidden Black Friday outcomes and demographic realism remain unverified.

## B. Requirements checklist

Primary sources reviewed: the supplied `Wevion-BigHack-sfida.pdf` (2 pages), `LEGGIMI.md.pdf` (4 pages), the project playbook (18 pages) and sign-up deck (18 slides). The challenge PDF and dataset guide take precedence over playbook claims. The public event page's judging criteria were also visible during browser inspection: [Codemotion event page](https://go.codemotion.com/big-hack-hackathon-2026-en/).

| Requirement | Initial status and evidence | Revised status / remaining gap |
|---|---|---|
| Imagine and justify audiences for all 12 ad sets | Twelve cards existed, but identities came from ID suffixes (`02678af:src/audiences.py:18–77,95–96`). | Twelve metric-derived hypotheses, alternatives and confidence in `out/audiences.json`. Demographics remain unobserved; synthetic viewers are explicitly hypothetical. |
| Daily CTR and CPM for every required ad/day, 16–30 Nov | Passed: 699/699 unique keys, correct metadata/order, positive finite predictions and ordered bands. | Regenerated and checked before writing by `src/contracts.py:6`; all 699 still pass. |
| Use creative, context, budget, fatigue and seasonality where supported | Implemented: shared feature builder and tree/ridge training. Keyword tagging rather than image analysis or an LLM. | Preserved, input joins checked, monthly features respect forecast cutoffs. Novel Black Friday effects remain a prior-year transfer assumption. |
| Recommend budget, creatives, levers and timing | Implemented, but averaging and one-size elasticity weakened the justification. | Daily bounded allocation scenarios, common-date comparisons and uncertainty-aware test recommendations. No causal or sales-lift claim. |
| Working repository application and generated predictions | Initial dashboard loaded; creative scoring crashed without `model.pkl`. | App controls and creative scoring pass executed tests; missing model rebuilds locally. |
| Methodology / audience reasoning in README and three-minute video | README/playbook existed. No video artifact or verified video link was found in the workspace. | README, this audit, `DESIGN.md`, and `DEMO.md` supplied. Video recording/link is still outstanding. |
| Optional new creative capability | Real forecasting implementation, but not executable in supplied checkout until model regeneration. | Working scoring, segment-specific tag sensitivities and viewer scenarios. It evaluates supplied concepts; it does not autonomously generate new ad assets. |
| Disclose tools and simulated nature of data | README disclosed tools; public challenge wording referred to real ads, while the detailed kit explicitly says simulated. | Detailed organisers' kit is treated as authoritative. UI/docs clearly say simulated; no external ad outcomes used. |

The source guide describes CTR/CPM as central examples and allows other KPIs/formats. The detailed challenge PDF explicitly asks for both; this implementation supplies both. A demographic chatbot panel is not an explicit mandatory deliverable in the detailed PDF, though the public challenge wording makes audience simulation part of the product expectation.

## C. Model evaluation

### Independently reproduced original results

Executed in a temporary copy of the initial code, with Python 3.12.14, scikit-learn 1.8.0 and the installed dependencies subsequently pinned in `requirements.txt`. Source history: 1,879 rows. Excluded: 10 suspected anomalies. Training: 1,426 rows through 1 Nov. Validation: 443 cleaned rows on 2–15 Nov.

| Metric | Naive last-seven-day baseline | Original deployed blend | Verification |
|---|---:|---:|---|
| CTR MAE | 0.316 percentage points | 0.228 percentage points | Reproduced |
| CTR MAPE | 33.3% | 25.6% | Reproduced |
| CTR global Spearman | 0.65 | 0.85 | Reproduced |
| CTR winning ad per set | 4/12 | 11/12 | Reproduced |
| CPM MAPE | 8.6% | 7.2% | Reproduced |
| CPM global Spearman | 0.96 | 0.97 | Reproduced |
| Original later-week CTR interval coverage | — | 71% versus 80% target | Reproduced |
| Original later-week CPM interval coverage | — | 83% versus 80% target | Reproduced |

The original table is preserved at `out/audit/original_validation.csv`; the original forecasts at `out/audit/original_predictions.csv`. Original numeric regeneration matched the supplied forecast file exactly. The current point forecasts also have maximum absolute change **0.0000** for both CTR and CPM.

MAE/MAPE are unweighted across ad-days. Ranking and winners use each ad's unweighted mean KPI across the evaluation window. Global Spearman ranks different audiences together, which is easier than selecting within an audience. The revised table adds within-set Spearman: **0.66 CTR, 0.43 CPM**. NDL-AS1's original within-set CTR correlation was **−0.50**, despite the strong global score. Thus “0.85 ranking correlation” must not be described as within-audience creative accuracy.

Ridge alone achieved 24.0% CTR MAPE, and the tree with the index achieved 6.8% CPM MAPE on this window. The fixed blend is not the per-metric November winner. Three earlier 14-day folds were added, ending before 2 Nov. The blend has lower mean log error than the other learned candidates for both metrics. The baseline remains competitive for CPM; averaged earlier-fold CPM MAE is approximately 0.723 versus 0.726 for the blend. No claim that complexity always wins is justified.

These earlier comparisons were added after examining November results, so the overall process is not a pristine blind model-selection experiment. None of the hidden 699 outcomes was available.

### Cold start, raw outcomes and subgroups

| Official-window subset | Rows | CTR MAPE | CPM MAPE | Interpretation |
|---|---:|---:|---:|---|
| Known ads | 377 | 24.0% | 6.6% | Stronger than cold start |
| New ads | 66 | 34.7% | 10.4% | Material degradation |
| Skincare | 147 | 26.2% | 7.3% | CTR winner 3/4; CPM winner 0/4 |
| Pet | 148 | 27.9% | 7.2% | CTR winner 4/4 |
| Clothing | 148 | 22.7% | 7.1% | CTR winner 4/4 |

Counts above should be read alongside the generated breakdown, which is the machine-readable source. In the cold-only subset, “12/12 winners” is **uninformative**: only one new ad per ad set is present. Cold-start forecasting is supported by measured errors, not by that trivial winner statistic.

Including all 444 supplied validation outcomes changes CTR MAE from 0.228 to 0.229 and WAPE from 19.2% to 19.3%; CPM MAPE remains 7.2%. MAPE's denominator is undefined at the additional zero CTR, so the table explicitly reports 443 positive denominators. All-row MAE/WAPE include the zero. The result does not depend heavily on that exclusion, but “confirmed tracking outage” is unsupported.

### Intervals: original claims versus current method

The 2–8 Nov calibration week contains **189 known-ad rows and zero new-ad rows**. The original implementation therefore used the constant 0.4 for cold-start log widths (`02678af:src/model.py:100–101`), including CPM, rather than learning cold-start width from that week. The original 71%/83% coverage numbers were real executed results, but the explanation that all widths came from measured calibration errors was incomplete.

The revised fallback uses 63 new-ad observations from an earlier temporal holdout, and the finite-sample order statistic replaces interpolated quantiles. On the untouched later week, current coverage is:

| Later week | Rows | CTR coverage | CPM coverage |
|---|---:|---:|---:|
| All | 254 | 70.9% | 76.0% |
| Known ads | 188 | 66.5% | 77.7% |
| New ads | 66 | 83.3% | 71.2% |

This is more traceable, **not evidence of improved coverage**. The 80% target remains unmet. Daily observations are temporally and creatively dependent, and production refits the model before transporting widths. Distribution-free conformal coverage cannot be assumed. Period-average bands and joint CTR/CPM probabilities are not validated.

### Leakage and extrapolation findings

- Verified: target outcomes are absent from inference features; encoder/scaler fitting happens within training. The official Nov split uses only rows through 1 Nov for fitting. No major outcome leakage was found in that protocol.
- Qualification: quality exclusions were chosen retrospectively after inspecting the whole supplied history, including a validation zero. That introduces selection bias into the cleaned evaluation. The all-row MAE/WAPE sensitivity quantifies its small observed effect; it does not make that cleaning decision prospective.
- Verified: subtracting 364 days correctly aligns weekdays, Black Friday week and Cyber Monday. The seasonal prior is prior-year supplied information, not hidden 2026 outcomes.
- Fixed during development: earlier rolling folds initially reused the realised full current-month market median. The revised forecast context exposes monthly observations only after month-end. The corrected earlier-fold results are exported.
- Remaining concern: November-to-Black-Friday transfer has no analogous observed event in the training target data. Event indicator columns cannot learn a new event when they are constant during training. The weekly index also remains a learner input, so detrending does not impose an independent fixed seasonal elasticity.
- Remaining concern: many creative tags are correlated with asset IDs, format, advertiser and launch date. One-tag sensitivities can be off-support and are not causal edit effects.

## D. Code and application review

The original implementation comprised 819 lines across `app.py` and five modules. No API/backend service is required; Streamlit calls local Python functions. Original output CSV/JSON files were data artifacts, not a substitute for training: actual reproduction confirmed the models generated them.

Executed original application check: initial Streamlit load had no exceptions; clicking the new-creative prediction button raised `FileNotFoundError` at `src/score_new.py:29`. The revised application rebuilt/scored successfully, retained form results across scenario controls, and handled a zero-total age mixture with a user-facing error.

The revised first screen now names a candidate and its actual creative description, presents a common-date ranking, and defines CTR/CPM/CPC. It exposes audience alternatives, bounded allocation scenarios and validation exports. The forecast screen was visually inspected in Chrome. Streamlit's test runner exercised all 12 segment selections, three advertisers, all KPI choices, both decision windows and the creative/viewer flow. Mobile layout and video playback were not inspected.

There was no model persistence version contract or stale-artifact check initially. The revised creative lab fingerprints training sources/data and rebuilds stale or absent local artifacts. The batch manifest records versions, training/calibration dates and output validity. Raw data and initial outputs are preserved. Pickle remains a trusted local artifact, not an upload format for arbitrary users.

## E. Critical issues, ranked

Initial source references below are immutable locations in commit `02678af`, obtainable with `git show 02678af:<path>`. Current fixes refer to the updated files.

| Priority / issue | Verified evidence and consequence | Fix, value and current status |
|---|---|---|
| **P0: new-creative feature fails in supplied checkout** | Initial `src/score_new.py:28–29` unconditionally loads a missing, ignored pickle; initial `app.py:106` propagates the exception. A live demo fails on its main interaction. | **Fixed.** `src/score_new.py:31` rebuilds absent/stale models. Tested through the application runner and missing-artifact integration test. High value, low difficulty. |
| **P0 deliverable gap: no recorded video evidenced** | Official PDF p.2 requires a three-minute video; no video/link was found in repository contents. A complete submission cannot be claimed. | **Still outstanding.** `DEMO.md` provides timed narration and submission copy. Recording and checking a link are worthwhile and essential; the task did not authorize platform submission. |
| **P1: demographic audience claims exceed the data** | Initial `src/audiences.py:18–77,95–96` assigns ages, income, placement and audience type from an ID suffix. These labels do not drive forecast responses. Judges can challenge the central simulation story. | **Partly resolved.** `src/audiences.py:49` uses measured profiles and permits ambiguity. `src/simulation.py:20` adds calibrated viewer scenarios with explicit assumptions. No available fix can make demographics empirically identifiable without new data. High value; moderate effort already completed. |
| **P1: interval coverage and provenance overstated** | Initial `src/model.py:92–101,173–176`: 80% target misses at 71% CTR; no cold rows in first calibration week, so width 0.4 is heuristic. Averaged daily bounds were labelled as 80% period bands. | **Partly resolved.** Explicit finite-sample rule, earlier held-out cold errors, provenance and subgroup coverage added at `src/model.py:102,159,237`. UI distinguishes daily from aggregate intervals. Undercoverage remains; do not claim calibrated 80% certainty. Worth fixing provenance now; new seasonal calibration evidence is unavailable. |
| **P1: unsupported causal budget curve and delivery averaging** | Initial `src/decide.py:14–16,33–45` assumes one elasticity for all sets/campaigns, averages CPC instead of aggregating click efficiency, and can increase recipients well beyond 20%. A one-week budget change also changes season/creative/fatigue. | **Fixed as scenario decision support, not causal identification.** `src/decide.py:42` optimizes daily click scenarios using explicit equal shares, bounded changes, cent conservation and adverse sensitivity. Actual uplift remains unproven. High value, moderate difficulty. |
| **P1: validation headline conceals weak creative ranking** | Initial `src/model.py:142–156` computes global correlation across audiences. Original NDL-AS1 within-set CTR correlation is −0.5; cold-only winners are singleton comparisons. The model may forecast broad audience differences while missing the creative decision. | **Fixed reporting; accuracy limit remains.** `src/model.py:208,237,299` exports within-set, advertiser, date, raw-row and cold-start diagnostics plus earlier folds. High value, moderate effort. |
| **P1: Black Friday accuracy not demonstrated** | Initial `src/features.py:109–126` and `src/model.py:39–51` transfer 2025 seasonality. No observed target event exists in training and the official validation ends beforehand. Hidden-test certainty is unsupported. | **Documented, not solved.** Alignment checked and exported. Retain prior with explicit uncertainty; no hidden outcomes exist to validate it. Essential explanation; external “real answers” cannot fix simulated-data uncertainty. |
| **P2: fatigue narrative mixes different creatives/cohorts** | Initial `src/audiences.py:83–84` compares all launch-week rows to all rows aged ≥28 days. “Week 4” includes every later age, and different ads contribute. Initial FGR-AS1 ratio 0.697 also contradicts the universal “almost no fatigue” story. | **Improved.** Same-ad first-observed-week versus later observations, adjusted by supplied seasonal index, with contributing ad count. Still descriptive and first-observed is not necessarily launch week. Low/moderate effort, worthwhile. |
| **P2: recommendations compare different date windows** | Initial `src/decide.py:65–76` averages an ad only over its active days, then compares with older ads spanning different dates. Average daily bounds become an unsupported confidence flag. | **Fixed.** `src/decide.py:106` aligns candidate dates and describes daily envelopes/test actions. High value, low effort. |
| **P2: missing contracts, fragile inputs and stale documentation** | Initial feature joins have no cardinality validation; app expects every artifact; README's generic winning-video narrative does not match every eligible set. | **Fixed.** Validated joins, actionable input errors, forecast contracts, manifest, pinned tested direct dependencies, dynamic creative descriptions and regenerated docs. Moderate value, low/moderate effort. |
| **P3: dense mixed-language product** | Original pages mix Italian/English and lead with a fingerprint table. The useful decision is hard to see in 30 seconds. | **Improved.** Consistent English campaign workspace, candidate first, terms defined, progressive detail. Desktop visually inspected; mobile not tested. Useful polish after model evidence. |

## F. Judge's scorecard

Subjective engineering assessment, not an official jury score or comparison with other teams. Criteria correspond to those displayed on the public event page. Scores assess the initial project, followed by the revised state.

| Criterion | Initial /10 | Revised /10 | Reason |
|---|---:|---:|---|
| Usefulness / value | 6 | 7 | Forecasts and decisions exist; revised allocation is bounded and uncertainty is visible. Sales value remains unmeasured. |
| Relevance | 7 | 8 | All daily forecasts and audience hypotheses delivered; viewer scenarios make the public brief easier to demonstrate. Demographic reactions remain assumptions. |
| Clarity / completeness | 5 | 7 | Reproducible point metrics, full diagnostics and explicit limits now present. Video still missing. |
| Design / UX | 5 | 7 | Decision-first workflow and explanations improve the initial dense tables. Limited desktop-only visual QA. |
| Creativity / innovation | 4 | 6 | Original pipeline is conventional forecasting; calibrated synthetic viewers and transparent sensitivity improve the product without pretending to generate evidence. |

| Technical area | Initial /10 | Revised /10 | Assessment |
|---|---:|---:|---|
| Prediction accuracy | 6 | 6 | Verified baseline improvement, same point predictions; cold-start and seasonal weaknesses remain. |
| Model reliability | 5 | 7 | Explicit temporal boundaries, contracts, artifact recovery and tests; interval calibration remains weak. |
| Data handling | 6 | 8 | Exact kit integrity, explicit exclusions, raw sensitivity, cardinality checks and complete forecasts. |
| Audience simulation | 3 | 6 | Behaviour-derived hypotheses plus calibrated hypothetical panel; individual truth is not observed. |
| Budget optimization | 3 | 6 | Daily constrained optimization and sensitivity; causal response and platform delivery remain assumptions. |
| Demo readiness | 4 | 7 | Working tested flow and recording script; no recorded video or submission verification. |

## G. Final improvement plan

Completed during this session: reproduce initial results; fix missing model; add output/data contracts; replace suffix-driven profiles; add controlled viewer simulation; improve budget scenarios and creative comparisons; expose raw, within-set, cold-start, temporal and interval diagnostics; add tests and rewrite documentation.

Priorities for remaining development hours:

| Order | Action | Value | Difficulty / realistic effort |
|---|---|---|---|
| 1 | Record the `DEMO.md` walkthrough and check repository/video links from another device or signed-out session. | Removes the outstanding mandatory deliverable risk. | Low, about 30–45 minutes including rehearsal and upload. |
| 2 | Rehearse answers on simulated data, demographic assumptions, 71%/76% current interval coverage, and untested Black Friday transfer. | Prevents the jury from finding contradictions between the demo and evidence. | Low, 15–30 minutes. |
| 3 | If more modelling time exists, predefine one interval-widening strategy using earlier folds, then evaluate on a genuinely fresh holdout when it becomes available. Report widths and coverage together. | Addresses the clearest unresolved statistical reliability problem. | Moderate; earlier-fold experiments fit within hours, but unbiased new-event validation needs unavailable outcomes. |
| 4 | Sensitivity-check creative rankings to plausible seasonal/budget stress and present unstable choices as experiments. | Helps avoid a brittle “pause” recommendation under an uncertain Black Friday prior. | Moderate, 1–2 hours; label scenarios rather than measured probabilities. |
| 5 | Only after the required video, consider mobile review or an Italian UI translation. | Improves accessibility and presentation, with little impact on forecast accuracy. | Low/moderate, 30–90 minutes. |

Do not spend the last hours adding an unvalidated chatbot panel, advertising outside-data training that did not occur, or switching to a more complex model without time-split evidence.

## H. Final blunt conclusion

1. **Does it satisfy the official challenge?** The implemented tool now covers the audience/forecast/decision requirements and all 699 rows. The complete submission still lacks a verified video link.
2. **Are the predictions credible?** Yes as baseline-beating small-data forecasts on the specified known window. No claim of proven Black Friday accuracy, causal budget lift or accurate demographic click rates is justified.
3. **Are Claude's metrics reproducible?** Yes: the original 25.6% CTR MAPE, 7.2% CPM MAPE, 11/12 CTR winners, 0.85/0.97 global correlations and 71%/83% original interval coverage were reproduced. Interpretations needed correction. Current interval coverage differs after the fallback change.
4. **Is the simulated audience convincing enough?** Original demographic labels were weak. The revised measured hypotheses and calibrated scenario panel are honest and demonstrable, but their demographic realism is unvalidated.
5. **Single biggest weakness?** Generalisation beyond the known window: new creative, an unseen seasonal event and undercovered uncertainty, with no hidden outcomes available to prove that transfer.
6. **Three highest-impact improvements?** Working fresh-checkout demo, explicit evidence-versus-assumption audience/decision layers, and stronger temporal/subgroup/interval validation. These are implemented; recording the required video is the remaining submission priority.
7. **Ready to submit right now? NO as a complete submission.** Code and prediction outputs are ready to demonstrate with their stated limits, but the required video must be recorded and its link verified. Do not claim guaranteed 80% coverage or a validated demographic simulator.

## Reproduction record

The initial audit used `/tmp/who-cares-original-20261114` to run existing validation/prediction commands without changing the repository's original outputs. Missing dependencies were installed in `/tmp/who-cares-audit-20261114`, outside the project. Additional experiment and test logs are in `/tmp/who-cares-*.log`; these are temporary, not submission dependencies.

Run the current `src/pipeline.py` to regenerate deliverables, and `python -m unittest discover -s tests -v` for the integration/UI checks. Final test results and input/output integrity checks are recorded in `out/audit/verification.json`. No source data was deleted, no hidden outcomes were retrieved, no remote repository was pushed, and no event submission was made.
