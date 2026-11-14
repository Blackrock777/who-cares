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
| Creative text (any language) | recommended | cold-start scoring; new-ad CTR error 0.32 with TF-IDF, 0.24 with the multilingual encoder |
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
| **adsim, multilingual HF encoder, no rules** | **0.173** | **25.1%** | **0.24** | **11/12** | **0.066** | **6.2%** |
| adsim, TF-IDF fallback (no download) | 0.176 | 27.0% | 0.32 | 11/12 | 0.066 | 6.2% |
| adsim + optional customer keyword tags | 0.171 | 24.6% | 0.22 | 10/12 | 0.066 | 6.2% |

Rule-based anomaly detection flags exactly the ten rows the submission listed by hand. Audience
archetypes clustered from behaviour reproduce the four-way structure without reading an ID.

## Pretrained models evaluated

| Model (Hugging Face) | Role tried | Result | Decision |
|---|---|---|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (ONNX via fastembed) | creative text encoder | new-ad CTR error 0.32 -> 0.24 vs character TF-IDF; language-independent | **adopted**, with TF-IDF fallback |
| `amazon/chronos-bolt-small` | zero-shot per-ad forecast for ads with history | CTR 0.205 vs engine 0.169; CPM 0.065 vs 0.064; cannot score new ads | rejected: no gain, heavy dependency |
| `Prior-Labs/TabPFN` v2 | replace boosted trees | **not run**: weights require accepting a licence interactively | harness ready (`TabPFNEngine` in the audit scripts); set `TABPFN_TOKEN` to test |
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

## What is not solved

- No conversions, revenue or ROAS: the reference data has none, and the engine predicts none.
- Seasonal peaks rely on the supplied index; without one, a first Black Friday is unforecastable.
- Audience demographics are not identifiable from aggregates and are not produced.
- Six embedding components and group penalties were set on this dataset. A second dataset is
  needed before calling them defaults.
