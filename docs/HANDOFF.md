# Handoff: the ad-forecasting project as it stands on 15 November 2026

Paste everything below into a new chat. It is written so that someone with no prior context can continue the work.

---

You are taking over an ad-performance forecasting project. Read this whole brief before touching anything. It describes what exists, how each part works, what has been proven, what has been disproven, and what is still open.

## 1. Where things are

- Project folder: `/Users/poojatalele/Desktop/ads`
- GitHub: `https://github.com/poojatalele/who-cares`
- Python: the working environment is `.venv` (Python 3.9). A second environment, `.venv312` (Python 3.12), exists only to test the TabPFN 3.5 model. Always run with `./.venv/bin/python`.
- Tests: `./.venv/bin/python -m unittest discover -s tests`. 38 tests pass on the current branch.
- Secrets live in three git-ignored files at the project root: `.env.tabpfn`, `.env.apify`, and optionally `.env.meta`. Never print them, never commit them.

### Branches

- `main`: the official hackathon submission. The remote `main` is two commits ahead of the local copy, so pull before working on it.
- `cpm-budget-season-audit`: merged into main already. It replaced the price model.
- `adsim-generic`: first version of the company-agnostic engine. Pushed.
- `adsim-bugfixes`: six robustness fixes to that engine. Pushed.
- `adlibrary-dataset`: the current working branch. Not pushed. It contains everything in `adsim-bugfixes` plus the Ad Library and Kaggle work, plus a fix for a missing advertiser level. It has two files with uncommitted edits: `adsim/adlibrary.py` and `scripts/fetch_apify_ads.py`. Commit those first.

## 2. What the project is for

It began as an entry to the Wevion BigHack 2026 hackathon (Wevion is part of Bhblasted, an Italian ad-tech company). The challenge, called "Clienti che non esistono", gave every team a simulated dataset and asked for a tool that does three things: infer who the audience of each ad set is, forecast click-through rate and cost per thousand impressions for every ad on every day from 16 to 30 November 2026 (a window that includes Black Friday), and help decide budget, creative and timing.

The organisers' kit is in `data/raw`. It holds three fictional Italian advertisers on Meta (skincare, pet food, clothing), 12 ad sets, 36 creatives described only in written Italian text (there are no images), 69 ads, 91 days of daily results from 17 August to 15 November 2026, and 699 ad-days to predict. The audience of each ad set was deliberately removed. The kit also includes a weekly market index for autumn 2025, monthly market prices, daily budgets including the future window, and a calendar.

After the hackathon work, the owner asked for the same method to be rebuilt as a product that any company could adopt with its own data. That second system is called `adsim`.

So there are two systems in this repository. They share a method. They do not share code.

## 3. System one: the hackathon submission, in `src/` and `app.py`

This produces the official forecast file `out/predictions.csv`. Treat `src/`, `app.py`, `data/raw` and the files directly under `out/` as frozen. Every later piece of work verified by checksum that these stayed byte-for-byte unchanged, and you should keep doing that.

### How data flows through it

One script, `src/pipeline.py`, runs the whole thing in order: rolling validation, the official validation, the forecast, the audience evidence, and the decisions.

`src/features.py` builds one row per ad per day. It joins the daily history to the creative descriptions, launch dates, starting budgets and the calendar. It removes ten rows it considers data traps: eight pet-advertiser rows on 14 October with zero clicks, one clothing row on 21 October where an ad set spent four times its budget, and one skincare row on 9 November with zero clicks. These exclusions are listed by hand in this file and exported to `out/quality_flags.csv`.

It then computes features. Creative features come from keyword rules applied to the Italian visual description: whether there is a hook in the first two seconds, whether someone talks to camera, whether a person appears, whether the creative is heavy with text, whether the logo comes first, whether the discount is revealed only at the end, plus timer, studio background, crossed-out price, reviews and black background. It also extracts the discount percentage from the headline, the format, video length, text lengths and the button text. Other features are the ad's age in days, the weekday, the ad set's budget and its ratio to the starting budget, and the 2025 market index for the matching week one year earlier, shifted by 364 days so weekdays and Black Friday line up.

### The click-through-rate model, in `src/model.py`

Two learners predict the logarithm of click-through rate after dividing out the 2025 seasonal index. One is a gradient-boosted tree. The other is a ridge regression. Their predictions are averaged equally and the seasonal index is multiplied back in. The ad set a row belongs to is also labelled by the last character of its identifier, which is a shortcut specific to this dataset.

### The price model, in `src/cpm.py`

Price is forecast separately, because an audit found two serious faults in using the same blend for price. First, seven of the twelve ad sets have Black Week budgets between 1.25 and 2.5 times their starting budget, while the history contains exactly one budget change. The tree returned no budget response at all on the forecast rows. Second, the ridge had learned a seasonal correction that cancelled about 12 percent of the Black Friday lift.

The price model fixes both. It estimates one budget elasticity, about 0.31, meaning price rises with budget raised to that power, using a ridge regression that controls for ad effects and fatigue. It then removes that budget effect and the seasonal index from the target and fits three learners on what is left: a ridge with group-specific penalties so that ads borrow strength from their creative and ad set, a gradient-boosted tree, and the ad's own average over its last seven days. The forecast is the average of the three, with the season and budget effects multiplied back. New ads use the first two only. The seasonal index used here is de-noised: the three sectors' curves are averaged and then fitted with a shape that only rises to the Black Friday peak and only falls after it. This was done because 2026 prices follow the trend of the 2025 index but not its week-to-week wiggles.

### Uncertainty

Ranges are empirical. The model is trained up to 1 November, its errors on 2 to 15 November are measured, and the 80th percentile of those errors becomes the band, separately for ads with history and brand-new ads.

### Audiences, decisions and the app

`src/audiences.py` describes each ad set from measured behaviour: response, price, frequency, fatigue and matched creative comparisons. It presents audiences as hypotheses with a confidence level and alternative explanations, not as facts, and does not invent demographics. `src/decide.py` runs a daily budget optimisation that keeps each campaign's total fixed and limits any ad set's change to 20 percent, under an assumed click elasticity of 0.42 with a sensitivity range. `src/simulation.py` draws an illustrative panel of imagined viewers whose average matches the forecast; age has no learned effect there. `src/score_new.py` scores a creative that does not exist yet. `app.py` is a Streamlit app that shows all of it.

### Measured accuracy of system one

Trained to 1 November and scored on 2 to 15 November, which is the organisers' own suggested check: click-through-rate error about 25.6 percent against 33.3 percent for a last-seven-days baseline, the best ad picked correctly in 11 of 12 ad sets, and price error about 6.3 percent against 8.6 percent. Twelve ads in that window were brand new to the model. That window has been looked at many times, so treat it as a regression benchmark and not as an untouched test.

## 4. System two: `adsim`, the company-agnostic engine

This lives in the `adsim/` folder. Its specification is `docs/BUILD_BRIEF.md` and its results and adoption notes are `docs/ADOPTION.md`. Read both.

The idea is that a new company writes one configuration file that maps its own column names onto a standard layout, and no code needs to change. Three configurations exist in `configs/`: the hackathon kit, a minimal history-only example, and a public Kaggle file.

### The standard layout

One row per ad per day. Required: date, ad, audience, creative, impressions, clicks, spend. Optional: reach, daily budget, advertiser, creative text, launch date, a seasonal index, external evidence.

### `adsim/data.py`: loading and quality rules

It reads the tables named in the configuration, renames columns, computes each ad's age, the budget relative to a reference budget, and attaches the seasonal index if one is supplied. The reference budget is the first budget ever observed for that audience, chosen because it can never leak later information into an earlier training window.

Quality flags are computed by rule, never by a hand-written list. A row is "invalid" if it is impossible, for example more clicks than impressions. It is "suspicious" if it has zero clicks where that ad's own click rate made that a less than one-in-a-thousand event, or if an audience's ads together spent more than 1.5 times the daily budget. Everything else is valid, including ordinary zero-click days. On the hackathon kit these rules rediscover exactly the ten rows that system one lists by hand.

### `adsim/creative.py`: reading the creative

Ad text is turned into numbers by a pretrained multilingual sentence encoder from Hugging Face, `paraphrase-multilingual-MiniLM-L12-v2`, run locally through the `fastembed` library. If that is unavailable it falls back to a simple character-pattern method that needs no download. The resulting vectors are compressed to a few components. By default that compression is learned only from creatives present in the training rows, so an evaluation of a genuinely new creative cannot peek at it. A configuration switch allows the looser protocol, which must be labelled as such. Customers can optionally add their own keyword rules through the configuration. There is also a hook for external evidence such as an ad-library export, which adds one extra feature; it runs but has never been validated.

### `adsim/engine.py`: the model

The model treats each performance number, on a logarithmic scale, as a sum of effects: the advertiser's level, the audience's level, the creative's effect, the individual ad's effect, a fatigue trend with ad age, the season, and budget pressure.

The core learner is a ridge regression with different penalty strengths for different groups of effects. Advertiser and audience levels are penalised lightly, creative and ad effects more, interactions more still. This is what lets an ad with little history fall back on its creative, its audience and its advertiser.

Season enters only by dividing the target by the index before fitting and multiplying it back afterwards, so no learner can cancel or exaggerate it.

Budget enters through one elasticity per metric. It starts from a shipped prior (0.3 for price, minus 0.1 for click-through rate) and moves toward what the customer's own budget changes show, in proportion to how much budget variation their history holds.

Audiences are grouped into behavioural types by clustering each audience's response, price and repeat exposure relative to its own advertiser. No names or identifiers are read. These types are used for fatigue slopes and interactions with creative attributes.

Click-through rate has two modes. When every training row has clicks, it uses the logarithmic model above. As soon as valid zero-click rows exist, it switches to a count model that treats clicks as a Poisson count with impressions as exposure, so zero-click days are modelled and never dropped or replaced by a small constant.

For price, the default forecast averages three learners: the ridge, a gradient-boosted tree, and the ad's own recent level. For click-through rate the default is the ridge alone. Identifiers with more than 200 distinct values are kept out of the tree and handled by the ridge in sparse form.

Calibration holds out the most recent days, up to 14 and never more than a third of the history, forecasts them with a model that did not see them, and measures two things. The first is the spread of observed daily values around the forecast. The second is the spread of the underlying rate, with click-count noise mathematically removed. With too little history it produces no range and says so in plain words.

Every forecast row carries flags saying whether the ad is new, the creative is new, the budget is outside the range seen in training, or the season is beyond what training saw.

### `adsim/simulate.py`

Three functions. The budget what-if returns a curve of price, click-through rate, impressions, clicks, cost per click and marginal clicks per extra euro across budget multipliers, with a note stating how many training rows had a budget change. The Monte Carlo simulation draws the underlying rate from the calibrated rate error, then adds click-count noise once, and reports ranges plus each ad's probability of being the best in its audience that day; ties share the win. The audience function describes each audience in behavioural terms.

### `adsim/evaluate.py` and the command line

`backtest` runs rolling-origin validation and reports metrics that stay meaningful when clicks are zero, counts every excluded row by reason, and reports range coverage separately for known and new ads. The command line is `python -m adsim <config> <command>` with commands `forecast`, `audiences`, `whatif`, `simulate`, `creative` and `validate`. Outputs go to `out/adsim/`, which is git-ignored.

### `adsim/adlibrary.py`

Converts Meta Ad Library records, either from the official interface or from a third-party scraper, into an ads table and a reach-by-age-and-gender table, with a split that keeps 40 percent for training and 60 percent for testing, grouped so that the same ad text never appears on both sides.

## 5. What has been measured

### On the hackathon kit, four rolling time windows

The generic engine matches the hand-tuned submission: click-through-rate error on a log scale of about 0.174 against 0.179, price error about 0.066 to 0.067 for both, and 33 or 34 of 40 best-ad picks correct. It does this with no Italian keyword rules and no identifier shortcuts.

### Pretrained models tested, all on the same four windows

- The multilingual sentence encoder is adopted for language coverage. An early claim that it cut new-ad error by a quarter was wrong; under the strict protocol it and the simple fallback are within noise of each other.
- Chronos, a time-series foundation model, was rejected. It was worse on click-through rate and equal on price, and it cannot score new ads.
- TabPFN version 3 and version 3.5, a tabular foundation model, were tested as a replacement for the trees. Version 3.5 gave a small consistent gain on price, about 1.7 percent relative, and nothing on click-through rate. It is not adopted because the gain is small, the licence is non-commercial, and it needs Python 3.10 or later.

The recurring lesson: the accuracy comes from the structure around the learner, not from the learner.

### Robustness fixes, each with a regression test

Six defects were reproduced and fixed: crashes on one audience, one creative, seven days of history and empty history; every zero-click day being dropped; a crash above 255 distinct identifiers; the first ad winning every simulated tie; click noise being counted twice in simulation; and training being able to see data after its cut-off. On a low-volume copy of the kit, where one impression in forty was kept, the click-through-rate bias went from plus 32 percent to minus 2 percent.

### A public Kaggle file, and a rejected claim

`configs/kaggle_sales_conversion.json` runs the engine on a public file of 1,143 rows described by its uploader as anonymised Facebook ads, broken down by campaign, age band, gender and interest code. Its provenance is unverified and it shows signs of filtering.

An earlier write-up claimed the engine beat the strongest baseline in 8 of 8 splits. An independent adversarial reviewer rejected that, correctly. A plain Poisson regression of about fifteen lines beat the engine in every split, and the engine had no advertiser-level term, so it under-predicted clicks by 19 and 38 percent in the two smaller campaigns. That bug is fixed. The engine now roughly ties the plain regression and remains slightly behind it. The withdrawn claims and the reviewer's findings are written up in `docs/ADOPTION.md`.

### Sephora ads from the Meta Ad Library

`data/external/ad_library/sephora/` holds 1,139 ads from the Sephora France and Sephora Italia pages, pulled through an Apify scraper under the owner's account for under one dollar. Each ad has its text, run dates, format, the advertiser's declared targeting, total EU reach, and reach split by country, age band and gender. It has no clicks, click-through rate, price or spend, so it cannot test the forecasts.

The first test on the held-out 60 percent found that ad text predicts almost nothing about who an ad reaches. Declared targeting and format explain a little, and most variation is unexplained. This is a negative result. A second adversarial review of this dataset and this result was launched and its verdict had not been received when this brief was written. Do not present the Sephora result as settled until that review is read. Its working folder is `/private/tmp/claude-502/-Users-poojatalele-Desktop-ads/505e5fa8-7353-413c-a628-5be641762159/scratchpad/review_sephora/`, which may not survive a new session, so rerun the review if it is gone.

## 6. Known weaknesses, stated plainly

- Everything about forecasting over time is validated on one simulated dataset. This is the biggest limitation and no modelling fixes it. A second advertiser's real daily performance data is what is needed.
- The budget rule rests on one budget change in one ad set and is extrapolated to 2.5 times.
- The Black Friday forecast relies entirely on last year's index. It cannot be validated before the hidden results exist.
- How click-through rate responds to budget is not identifiable from the data. Two estimates disagree.
- Ranges for brand-new ads are too narrow, covering about 68 percent against an 80 percent target.
- Low-impression rows click far less than their group's rate implies, and the engine treats impressions as a given.
- No model tried, including this one, can forecast a campaign it has never seen.
- The price model is the wrong design for accounts billed per click, where spend is zero whenever clicks are zero.
- Nothing predicts sales, revenue or return on ad spend.
- Age, gender and income cannot be recovered from click and price totals, and the tool does not claim to.

## 7. How to work on this

- Keep `src/`, `app.py`, `data/raw` and the top-level files in `out/` unchanged, and verify by checksum after any change.
- Reproduce a problem before fixing it, and add a regression test with every fix.
- Compare before and after on identical splits, and report excluded rows so that dropping hard rows cannot pass as an accuracy gain.
- Before reporting any result as a win, hand the data, the code and the claim to an independent reviewer instructed to reject it. This caught a false claim once already.
- Do not push or merge without being asked.
- External datasets are git-ignored. `scripts/fetch_kaggle_sales_conversion.sh` and `scripts/fetch_apify_ads.py` recreate them.

## 8. Sensible next steps

1. Commit the two uncommitted files on `adlibrary-dataset`.
2. Obtain and read the adversarial review of the Sephora dataset, then correct the dataset builder and the conclusions accordingly.
3. Decide with the owner whether to merge `adlibrary-dataset` into `main`, after pulling the two newer remote commits.
4. Find a second real dataset with daily ad-level results. Without one, further model work is tuning against noise.
5. If accounts billed per click matter, build a cost-per-click model and derive spend from predicted clicks.
6. The hackathon itself still needed a three-minute video, scripted in `DEMO.md`.
