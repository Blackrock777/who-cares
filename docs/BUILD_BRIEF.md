# Build brief: a pre-launch advertising simulator any company can adopt

This is the prompt the engine in `adsim/` was built against. It is written to be handed to an
engineer or an AI coding agent unchanged.

---

<role>
You are the lead ML engineer on a product team shipping forecasting software to media buyers and
agencies. You have run paid-social accounts yourself. You distrust demos and you measure everything.
</role>

<product>
A pre-launch simulator for paid-social campaigns. A customer connects their own ad history. The
product answers four questions before money is spent:
1. Will this ad work, for which audience, and how sure are we?
2. What happens to price and response if I raise or cut the budget mid-flight?
3. Who is behind each audience, judged by behaviour, and what should I show them?
4. Which creative should I run, pause or test next?
</product>

<hard_requirements>
- **No customer-specific code.** No hard-coded IDs, dates, brand names, languages, verticals or
  anomaly lists. Everything customer-specific lives in one config file that maps their columns to
  the canonical schema. Adding a customer means writing a config, not code.
- **Works from sparse data.** A new customer may have 30 days of history, one platform, no
  seasonal benchmark and no audience labels. Every optional input must degrade gracefully and the
  output must say which inputs were missing.
- **Cold start is a first-class case.** A creative with zero history must be scoreable from its
  copy and description (and later its pixels), in any language.
- **Counterfactuals must be structural.** Budget and season effects are extrapolations by nature.
  They must come from an explicit, inspectable response function with stated parameters, never
  from a learner that silently returns its nearest training value.
- **Every number carries uncertainty** calibrated on held-out time, and every forecast states
  whether it is interpolation (seen conditions) or extrapolation (unseen budget, season, creative).
- **Borrow strength, then adapt.** Ship priors (pretrained encoders, cross-account or public
  evidence such as ad-library longevity) and let each customer's own data override them as it
  accumulates. Never present a prior as a measurement.
</hard_requirements>

<canonical_schema>
One row per ad per day. Required: date, ad_id, audience_id (ad set), creative_id, impressions,
clicks, spend. Optional: reach, daily_budget, advertiser_id, vertical, creative text fields
(headline, body, cta, visual description), creative launch date, a market seasonal index, a
calendar of events, external creative evidence.
</canonical_schema>

<method_constraints>
- Model rates on a log scale as a product of interpretable factors:
  audience level x creative effect x fatigue x season x budget pressure x noise.
- Use partial pooling: an ad borrows from its creative, its audience and its advertiser in
  proportion to how little data it has.
- Represent creatives with a pretrained multilingual encoder so that the same code reads Italian,
  English or Hindi copy. Hand-written keyword rules are allowed only as an optional, configurable
  extra, never as the only path.
- Evaluate any pretrained or foundation model (tabular, time-series, text) against the simple
  structural model on rolling-origin splits before adopting it. A complex model must earn its place.
- Detect data-quality anomalies by rule (statistically impossible click counts, spend above
  budget), record them, and report results with and without them.
</method_constraints>

<audience_simulation>
Audiences are not given. Infer behavioural archetypes from each audience's fingerprint (price,
response, frequency, fatigue speed, sensitivity to creative features) by clustering, without using
names or IDs. Then expose a simulator: for any creative x audience archetype x budget x day,
draw impressions, reach and clicks from the fitted model so the user sees a distribution, not a
point. Demographics that the data cannot identify must not be invented.
</audience_simulation>

<evaluation>
Rolling-origin validation with at least three cut-offs. Report per KPI: log error, MAPE, bias,
within-audience rank correlation, winner selection, cold-start error, and interval coverage.
Report the budget what-if separately on any natural experiment present in the data. State
plainly what cannot be validated.
</evaluation>

<deliverables>
1. A package with `fit`, `forecast`, `what_if_budget`, `score_creative`, `simulate` and
   `audiences` entry points, driven by one config file.
2. A config for the reference dataset proving that zero code changes were needed.
3. A comparison table: structural model vs pretrained alternatives, same splits.
4. An adoption guide: what a new customer supplies, what improves as data accumulates, and how
   to fine-tune each component.
</deliverables>

<anti_goals>
Do not build an LLM chat persona panel as the predictor. Do not report in-sample fit. Do not tune
on the final window. Do not claim sales, ROAS or profit effects from click and price data.
</anti_goals>
