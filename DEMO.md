# Three-minute demonstration and submission copy

## Recording preparation

Run the pipeline and open the application. Rehearse once with the creative form defaults and keep the generated CSV available. Record the local app; no account sign-in or external service is necessary. Avoid showing unrelated browser tabs, email or local files in the recording.

Required deliverables are the functioning repository, forecasts and reasoning including a three-minute video. The supplied sign-up deck says the platform also needs a title, description, video URL, repository URL and team contact. Its stated deadline is **15 November 2026 at 12:00**, in the event's Italy context. Check the platform's current checklist before submitting. This repository includes a script, not a video; nothing has been submitted automatically.

## Timed script: 180 seconds

**0:00–0:20 · Problem and result — Compare ads**

“Who Cares lets you rehearse an advertising campaign before spending. We predict how every ad will respond across twelve audience segments, show the uncertainty, and turn the forecasts into small decisions to test. This is the organisers' simulated dataset, not real customer data.”

Point at 699 forecasts, twelve segments and the held-out metrics.

**0:20–0:50 · Evidence — Validation & exports**

“We trained only through November first and predicted the next two weeks. Against the last-seven-days baseline, CTR error fell from 33.3 to 25.6 percent, and we selected the highest-CTR ad in eleven of twelve sets. CPM error was 6.3 percent, down from 8.6 for the baseline. We also report weak segments and new ads, where errors are larger. Black Friday results are still hidden.”

Show baseline versus blend. Do not call global correlation within-audience accuracy.

**0:50–1:15 · Audience — Audience evidence**

“The audience descriptions are hidden. We use observed click response, auction cost, frequency and fatigue to propose profiles, with alternative explanations. High repeat exposure and CTR suggest a warm audience, but cannot prove retargeting. Ages and income cannot be recovered from these aggregate records.”

Select a warm-response segment and point at its actual evidence.

**1:15–1:40 · Decision — Compare ads**

“Here is a candidate to test first, its actual creative description and its expected CTR and CPM. Candidates are compared over the same dates. The shaded ranges come from held-out errors. Coverage is below the nominal eighty-percent target, and the seasonal Black Friday pattern transfers from the supplied 2025 benchmark. We make that uncertainty visible.”

Show CTR, then CPM. Keep the overlapping-uncertainty action visible.

**1:40–2:05 · Money — Budget scenarios**

“This daily scenario preserves each campaign's budget and changes no segment by more than twenty percent. We assume equal ad delivery and diminishing returns. The screen shows the expected gain and adverse sensitivity, which can be negative. It recommends a controlled test, not guaranteed extra clicks or sales.”

Point at proposed budgets and downside sensitivity.

**2:05–2:45 · Before launch — Creative lab**

“Now we can score a creative that has never run. The same model forecasts response across all four audiences, and tag sensitivities help explain the differences. Those are model associations, not causal promises.”

Submit the default Italian description. Select one segment's explanation.

“The viewer panel illustrates people of different ages, needs and habits. Those details are assumptions, so we label them. Its probabilities are calibrated back to the segment forecast; changing a story cannot create extra forecast clicks. We never use simulated people to pretend we have new validation data.”

Show the viewer table and briefly move habit sensitivity.

**2:45–3:00 · Deliverables — Validation & exports**

“All 699 required ad-days are generated and checked for completeness. You can download them here, inspect the validation and regenerate everything from the original kit. The prediction is measurable; the assumptions are visible; the next decision is testable.”

End on the download button and validation evidence.

## Submission text

**Title:** Who Cares — Rehearse your campaign before you spend

**Description:**

Who Cares is an AI-assisted campaign rehearsal tool for the Wevion challenge. It forecasts daily CTR and CPM for all 699 required ad-days, compares creative performance across twelve audience segments and proposes bounded budget-allocation scenarios.

The CTR engine blends gradient-boosted trees and regularized regression; CPM uses a budget-aware ensemble on a de-noised seasonal index. Both use creative-description tags, segment identity, ad age, planned budgets and the supplied market/calendar benchmarks. On the specified 2–15 November validation window, trained through 1 November, CTR MAPE is 25.6% versus 33.3% for the naive baseline, CPM MAPE is 6.3% versus 8.6%, and the predicted highest-CTR ad matches the observed winner in 11 of 12 sets. Full subgroup, cold-start and earlier-window results are included.

Audience hypotheses come from measured behaviour, with confidence and alternative explanations. The creative lab scores a new concept across audiences and offers a hypothetical viewer panel calibrated to the statistical forecast. Ages, habits and needs are assumptions, not recovered demographics. Budget scenarios preserve daily totals, cap segment changes and expose downside sensitivity. Intervals are empirical and do not guarantee 80% coverage; Black Friday transfer remains untested on hidden outcomes.

All data is the organisers' simulated kit. Python, pandas, scikit-learn, SciPy, Streamlit and Altair power the application; Claude and Codex assisted development and review. The repository includes checked predictions, reproducible validation, source provenance, audience evidence, design documentation and an independent audit.

**Repository:** https://github.com/poojatalele/who-cares

**Video:** Add the recorded video URL. This is still outstanding.
