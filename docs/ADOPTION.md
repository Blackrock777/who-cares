# adsim: adoption guide

`adsim/` is the company-agnostic engine built against `docs/BUILD_BRIEF.md`. The hackathon
submission in `src/` is unchanged; `adsim` reproduces it from a config file with no code that
knows the kit's IDs, dates, language or anomalies.

## Run

```bash
python -m adsim configs/wevion_bighack.json forecast
python -m adsim configs/wevion_bighack.json audiences
python -m adsim configs/wevion_bighack.json whatif --audience NDL-AS4
python -m adsim configs/wevion_bighack.json simulate
python -m adsim configs/wevion_bighack.json creative --json configs/examples/new_creative_beauty.json --advertiser NDL-C1
```

Outputs land in `out/adsim/` with a `run.json` that records the encoder used, the fitted and
prior budget elasticities, band widths, anomalies excluded and which optional inputs were missing.

## What a new customer supplies

| Input | Required | What it buys (measured on the reference data, mean absolute log error) |
|---|---|---|
| Daily rows: date, ad, audience, creative, impressions, clicks, spend | yes | CTR 0.22, CPM 0.10 on 2-15 Nov with nothing else |
| Daily budget per audience | recommended | enables the budget what-if; own budget changes override the shipped prior |
| Creative text (any language) | recommended | cold-start scoring from copy; under the strict protocol the multilingual encoder and TF-IDF are within noise of each other on this data (new-ad CTR error 0.21 vs 0.22) |
| Seasonal market index | optional | CPM 0.10 -> 0.062 and removes an 8% under-prediction when the season is rising |
| Launch dates, reach | optional | fatigue from true age; frequency for archetypes and reach simulation |
| External evidence (ad-library export) | optional | one extra creative feature; weight decided by the customer's own data |

A config maps their column names to these (`configs/wevion_bighack.json` is the full example,
`configs/minimal_example.json` the smallest that runs).

## Generic engine vs the hand-tuned submission (four rolling windows, same splits)

| Model | CTR log err | CTR MAPE 2-15 Nov | New-ad CTR | CTR winners | CPM log err | CPM MAPE 2-15 Nov |
|---|---:|---:|---:|---:|---:|---:|
| Last 7 days | 0.210 | 33.3% | 0.37 | 4/12 | 0.084 | 8.6% |
| Submission (`src/`, Italian keyword rules, ID-based roles) | 0.179 | 25.6% | 0.26 | 11/12 | 0.067 | 6.3% |
| **adsim, multilingual HF encoder, no rules** (transductive protocol) | **0.173** | **25.1%** | **0.24** | **11/12** | **0.066** | **6.2%** |
| adsim, same, strict protocol (default since the robustness fixes) | 0.174 | 25.8% | 0.26 | 11/12 | 0.067 | 6.3% |
| adsim, TF-IDF fallback (no download) | 0.176 | 27.0% | 0.32 | 11/12 | 0.066 | 6.2% |
| adsim + optional customer keyword tags | 0.171 | 24.6% | 0.22 | 10/12 | 0.066 | 6.2% |

Rule-based anomaly detection flags exactly the ten rows the submission listed by hand. Audience
archetypes clustered from behaviour reproduce the four-way structure without reading an ID.

## Pretrained models evaluated

| Model (Hugging Face) | Role tried | Result | Decision |
|---|---|---|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (ONNX via fastembed) | creative text encoder | language-independent. An earlier figure (0.32 -> 0.24) came from fitting the text projection on creatives from after the cut-off; with the projection fitted on training creatives only it is 0.26 vs 0.27 on 2-15 Nov, within noise | **adopted** for language coverage, with TF-IDF fallback |
| `amazon/chronos-bolt-small` | zero-shot per-ad forecast for ads with history | CTR 0.205 vs engine 0.169; CPM 0.065 vs 0.064; cannot score new ads | rejected: no gain, heavy dependency |
| `Prior-Labs/tabpfn_3_5` and 3.5-fast | replace boosted trees | CPM error 0.0663 -> 0.0652 (all four windows); CTR unchanged; alone it is worse on CTR and new ads | not adopted: small gain, non-commercial licence, 900 MB, Python >= 3.10 |
| Boosted trees (scikit-learn) | interaction learner | weakest learned component for CTR in every window; useful for CPM in a blend | kept for CPM only |

Not tested here, and the order in which they become worth testing:
1. **Image/video encoders** (`google/siglip-base-patch16-224`, CLIP): only once customers supply
   pixels. They replace the written visual description, which is the strongest cold-start signal.
2. **A vision-language model** to produce the visual description automatically from the asset, so
   the text encoder path above works unchanged.
3. **Larger text encoders** (`intfloat/multilingual-e5-large`, `BAAI/bge-m3`): with 36 creatives
   the six principal components are the bottleneck, not encoder quality.

## How to fine-tune, in order of return

1. **Per customer, automatic.** Refit on every data refresh. Partial pooling already moves each
   ad from the prior toward its own data; the elasticity moves from the shipped prior (CPM 0.3,
   CTR -0.1) toward the customer's own budget changes. On the reference data it lands at 0.31
   and -0.21 from one budget event covering 0.7% of rows.
2. **Across customers.** Fit one model on pooled accounts with advertiser as a level. The creative
   block (embedding components -> effect) is what transfers. This is the main product moat and
   needs no new code: stack histories and add `advertiser_id`.
3. **Encoder head.** With a few thousand labelled creatives across accounts, train a small
   regression head on frozen embeddings (target: creative effect from step 2), then use its
   output as the creative feature. Only after that, fine-tune the encoder itself with a
   contrastive objective on winner/loser pairs from the same audience and week.
4. **Public evidence.** Add an ad-library export under `creatives.external_evidence` in the config:

   ```json
   "external_evidence": {"file": "data/ad_library_beauty.csv",
                         "text": ["headline", "body", "visual_description"],
                         "outcome": "days_running"}
   ```

   One row per external ad. `outcome` is any numeric longevity or reach proxy (days live, midpoint
   of the EU impression band). The engine learns "what tends to keep running" from it and adds
   one feature, `prior_longevity`, to every creative. Longevity is a weak label: it is survivorship
   among ads advertisers chose to keep, so the customer's own results decide its weight. This path
   is implemented and exercised by code, but **not validated**: no ad-library data was available.

## Audience simulation

`audiences` clusters ad sets into behavioural archetypes (A0 lowest response ... A3 highest) from
price, response and repeat exposure relative to the advertiser's own average. `simulate` draws
outcomes for every ad x audience x day: forecast uncertainty (calibrated on held-out days) times
click-count noise (Poisson at the simulated impressions). It returns ranges for impressions,
clicks, reach and observed CTR, and the probability that each ad is the best in its audience that
day. `creative` runs a not-yet-existing creative through every archetype. Age, gender and income
are not simulated because click and price aggregates cannot identify them.

## Budget changes mid-flight

`whatif` returns the response curve. On the reference data, for the beauty warm audience over
16-30 November: doubling budget raises CPM about 24% and lowers CTR about 14%, so clicks rise 39%
rather than 100%, and each extra euro buys 0.23 clicks against 0.33 at the planned level. Rows
are flagged `extrapolated` when the budget is outside what that customer's history contains.
Limits: the CPM response is supported by one natural experiment; the CTR response is not
separately identified (a matched comparison gives about zero, the model -0.21), so treat the click
curve as a range between the two.

## Robustness fixes (14 Nov), before and after on identical splits

Six defects were reproduced and fixed; each has a regression test in `tests/test_adsim_regressions.py`.

| Defect | Before | After |
|---|---|---|
| One audience, one creative, 7 days of history, empty history | crash inside scikit-learn | runs; no archetypes or text components where the data cannot support them; hold-out adapts (a third of the history, 3 to 14 days); with too little history no interval is reported and the output says so; empty history raises a clear error |
| Zero-click days | every zero-click row was flagged and dropped | three classes: invalid, suspicious, valid. Valid zero-click days are kept. CTR switches from log-normal to a Poisson count model with impressions as exposure as soon as valid zeros exist |
| More than 255 levels of an ID | tree crashed | such IDs are handled by the partially pooled linear model (sparse); the tree keeps their features; unseen levels are accepted |
| Simulation ties | first ad won every tie | tied ads share the win |
| Uncertainty | simulated ranges added Poisson noise on top of an error band that already contained it | calibration separates rate error from click-count noise; the simulator adds count noise once |
| Validation boundaries | quality flags, text projection and the reference-budget fallback could see rows after the cut-off | all three are computed from training rows only; the transductive creative protocol is opt-in and labelled |

Normal volume (the reference data, four windows, 1,309 scored rows). The fixes leave accuracy unchanged under the old protocol and cost a little under the strict one:

| | CTR log err | New-ad CTR | CTR winners | CPM log err | Simulated CTR range coverage, known / new ads (target 0.80) |
|---|---:|---:|---:|---:|---:|
| Before (projection saw later creatives) | 0.173 | 0.200 | 34/40 | 0.066 | 0.91 / 0.82 |
| After, same protocol (transductive, opt-in) | 0.173 | 0.200 | 34/40 | 0.066 | 0.82 / 0.72 |
| After, strict protocol (default) | 0.174 | 0.208 | 33/40 | 0.067 | 0.81 / 0.68 |

Low volume (the same rows with 1 impression in 40 kept and clicks thinned binomially; 365 of 757 scored rows have zero clicks; scored against the full-volume CTR of the same rows):

| | Training rows used | CTR log err vs truth | Pooled CTR bias | CTR winners |
|---|---:|---:|---:|---:|
| Before: zero-click days dropped | 940 | 0.485 | +32% | 6/24 |
| After: zero-click days modelled as counts | 1,278 | 0.253 | -2% | 18/24 |

Unresolved, stated plainly:
- **Ranges for brand-new ads are too narrow**: about 0.68 coverage against 0.80 for simulated CTR, and 0.76 to 0.80 for CPM. The hold-out usually contains few new ads, and new ads carry a bias the band does not model.
- The daily CTR band for known ads covers about 0.76; simulated ranges (0.81) are the better-calibrated output.
- The Poisson path is validated only on thinned copies of this dataset, not on a genuinely low-volume account.
- 2-15 November has been inspected many times and is a regression benchmark, not an untouched test.

## Second dataset: real campaign data from Kaggle

`configs/kaggle_sales_conversion.json` runs the engine, unchanged, on the public "Sales Conversion Optimization" dataset: 1,143 real, anonymised Facebook ads from three campaigns, one row per campaign x age band x gender x interest, with impressions, clicks and spend. It has no dates, creative text or budgets, 18% of rows have zero clicks, and the account is billed per click. Fetch it with `scripts/fetch_kaggle_sales_conversion.sh`; the file is not committed.

Protocol: 40% of rows train, 60% test, stratified by campaign, repeated over 8 random splits (the data has no time order). Task: predict clicks for unseen age x gender x interest cells.

| Model | Click error (WAPE) | Pooled bias | Poisson deviance | Error per age-gender audience |
|---|---:|---:|---:|---:|
| Campaign average rate | 0.243 | -1% | 2.97 | 19% |
| Campaign x age x gender average | 0.143 | -1% | 1.25 | 4.0% |
| Campaign x age x gender x interest average | 0.167 | -5% | 3.22 | 6.1% |
| **adsim** | **0.101** | **0%** | **0.81** | **2.6%** |

adsim was better than the strongest baseline in 8 of 8 splits. This is the first check of the zero-click path and of partial pooling on real low-volume data. What it does not test: forecasting over time, creative text, budget response or season, none of which this dataset contains.

What the data says about audiences (real, not inferred): click rate rises with age in every campaign and women click more than men in every age band (0.025% vs 0.017% at 45-49), while men convert more per click (65 vs 42 per thousand clicks at 45-49). The engine's archetypes separate women 35+ from the rest without being given age or gender as fields.

A defect this dataset exposed: with per-click billing, spend is zero whenever clicks are zero, and the log price model cannot take those rows. They are now left out of the price fit and counted in the output rather than crashing; a price model for click-billed accounts is not built.

Three other Kaggle datasets were downloaded and rejected as synthetic: uniform category counts, invented company names, identical click and impression values across rows.

## What is not solved

- No conversions, revenue or ROAS: the reference data has none, and the engine predicts none.
- Seasonal peaks rely on the supplied index; without one, a first Black Friday is unforecastable.
- Audience demographics are not identifiable from aggregates and are not produced.
- Six embedding components and group penalties were set on this dataset. A second dataset is
  needed before calling them defaults.
