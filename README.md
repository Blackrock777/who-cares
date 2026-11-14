# Clienti che non esistono · Wevion BigHack 2026

Uno strumento che immagina il pubblico di ogni ad set, prevede CTR e CPM giorno per giorno
nelle due settimane del Black Friday, e dice dove mettere il budget. Tutto a partire dal kit:
91 giorni di storico, 36 creatività descritte a parole, 3 inserzionisti simulati.

*A tool that infers who is behind each ad set, forecasts CTR and CPM per ad per day for
Black Week with error bands, and turns the forecast into budget, creative and timing decisions.*

## Run it

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cd src
../.venv/bin/python model.py validate   # train to 1 Nov, score 2-15 Nov
../.venv/bin/python model.py predict    # train on all 91 days, write out/predictions.csv
../.venv/bin/python audiences.py        # out/audiences.md, out/audiences.json
../.venv/bin/python decide.py           # out/decisions.md, out/decisions.json
cd .. && ./.venv/bin/streamlit run app.py
```

## The three deliverables

| # | What | Where |
|---|---|---|
| 1 | The tool | `app.py` (Streamlit): audiences, forecasts with bands, decisions, and a "score a new creative" page |
| 2 | The predictions | `out/predictions.csv`: for every row of `da_prevedere.csv`, `ctr_pred`, `cpm_pred` and 80% bands (`*_lo`, `*_hi`), plus `cold_start` |
| 3 | The reasoning | this README, `out/audiences.md`, `out/decisions.md`, and the 3-minute video |

## 1. Who is behind each ad set

The audiences are hidden, so we read them off the behaviour. The same four-way structure appears in
all three advertisers, which is how a Meta sales campaign is normally built. Full evidence per set
is in `out/audiences.md`.

| Ad set | Audience | The fingerprint that gives it away |
|---|---|---|
| 1 | Broad prospecting, cold | Biggest budget, lowest CPM, highest reach per euro, frequency 1.03, lowest CTR, almost no fatigue, Black Friday lever under-indexes |
| 2 | Interest / lookalike, deal-driven, younger | Mid CPM, fast fatigue (week-4 CTR is 70% of week-0), Black Friday lever over-indexes 1.2-1.7x, Saturday CTR higher, video and talking-to-camera beat images 1.3-1.7x |
| 3 | Narrow premium interest, older | Smallest budget but near-warm CPM, Black Friday lever under-indexes most (0.6-0.7x), scarcity and "talks to camera" get the biggest lift, no fatigue |
| 4 | Retargeting, warm | CTR 2x the cold sets, frequency 1.20-1.24 against 1.03, lowest reach per euro, strongest fatigue, Black Friday lever 1.35-1.6x, Friday-Sunday CTR above average |

## 2. How the forecast works

`src/features.py` builds one row per ad per day with:

- **Creative features** tagged from the Italian visual descriptions: hook in the first 2 seconds, someone talking to camera, a person on screen, heavy text or infographic, logo before the hook, discount revealed at the end, timer, studio background, crossed-out price, reviews, black background, discount percentage, format, video length, CTA.
- **Fatigue**: days since the ad launched. CTR falls from ~1.6% in week 0 to ~1.1% by week 8 in the history.
- **Budget**: the ad set's daily budget and its ratio to the initial budget. When NDL ad set 4 doubled its budget in the history, CPM rose 28% and CTR fell 14%.
- **Season**: the 2025 weekly market index for the same week (Black Friday week 2025: CPM 1.57x, CTR 1.24x), aligned 52 weeks back so weekdays match, plus the monthly market CPM.
- **Calendar**: weekday, weekend, event days.

`src/model.py` trains two learners on log(CTR) and log(CPM) **detrended by the 2025 index**, so the
Black Week lift comes from the index and the model only explains what is specific to each ad:

- a gradient-boosted tree (interactions: ad set x creative x fatigue),
- a log-linear ridge (extrapolates cleanly to budgets and index values the history never saw).

They are blended 50/50. Bands are conformal: the 80% quantile of absolute log error on a held-out
window, computed separately for ads with history and for cold-start ads.

Three data traps were removed before training: 14 Oct (every pet ad has zero clicks), 21 Oct
(FGR ad set 1 spent 4x its budget), 9 Nov (NDL-AD15 zero clicks).

## Validation (exactly the protocol in the brief)

Trained on data to 1 November, scored on 2-15 November. Twelve ads launched inside the window, so
they were cold-start for the model, the same situation as the four Black Friday creatives in the test.

| Model | CTR MAE (pp) | CTR MAPE | CTR rank corr | CTR winner per ad set | CPM MAPE | CPM rank corr |
|---|---|---|---|---|---|---|
| Naive: last 7 days per ad | 0.32 | 33% | 0.65 | 4 / 12 | 8.6% | 0.96 |
| Ours: tree + ridge, index-detrended | 0.23 | 26% | 0.85 | 11 / 12 | 7.2% | 0.97 |

Bands calibrated on 2-8 Nov covered 71% (CTR) and 83% (CPM) of 9-15 Nov at an 80% target.
All variants are in `out/validation.csv`.

## 3. Decisions (full tables in `out/decisions.md`)

- **Budget.** Cost per click = CPM / (10 x CTR). The warm set buys the cheapest clicks in pet and
  fashion; the deal-driven set 2 buys the cheapest in beauty. We move 20% of the most expensive
  set's budget there, with diminishing returns (clicks scale with budget^0.42, from the history).
- **Creative and lever.** In every cold ad set the Black Friday day creative with a fast hook and a
  person talking to camera wins (predicted CTR ~1.5%). The heavy-text "Black Friday anticipato"
  graphic loses everywhere (0.6-0.7%) and should be paused. In the warm set the "Black Week" unboxing
  video wins at ~2.4%.
- **Timing.** CPM steps up on 23 November and stays high through Cyber Monday; the price of
  attention in Black Friday week is about 20% above the week before, so the pre-week is where cheap
  reach lives and Black Week is where warm audiences convert.

## Beyond: score a creative before it exists

Tab 4 of the app takes a product vertical, lever, format and a description written like the kit's,
tags it, predicts CTR and CPM for each ad set over the Black Week window, and explains the
prediction by flipping one creative feature at a time ("if the discount were revealed at the end
instead of at the start, CTR -18%"). This closes the loop the brief describes: idea, simulated
audience, expected KPIs, before spending.

## Tools used

Python, pandas, scikit-learn, Streamlit. Claude Code was used to explore the data, write the
pipeline and draft this README; the modelling choices and the audience hypotheses were checked
against the validation window, not taken on faith.
