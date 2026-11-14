"""Bounded click-allocation scenarios. No causal budget or sales uplift is claimed."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

OUT = Path(__file__).resolve().parents[1] / "out"
# Scenario assumptions. One confounded budget change cannot identify a causal curve.
ELASTICITY = 0.42
ELASTICITY_RANGE = [0.25, 0.42, 0.7, 1.0]
MAX_CHANGE = 0.20
WEEKS = {"Pre Black Week (16-22 Nov)": ("2026-11-16", "2026-11-22"),
         "Black Week + Cyber Monday (23-30 Nov)": ("2026-11-23", "2026-11-30")}


def round_budget(amounts, original):
    """Cent rounding with conservation and per-set limits."""
    lower = np.ceil(original*(1-MAX_CHANGE)*100-1e-7).astype(int)
    upper = np.floor(original*(1+MAX_CHANGE)*100+1e-7).astype(int)
    scaled = amounts*100
    cents = np.clip(np.floor(scaled).astype(int), lower, upper)
    remainder = int(round(original.sum()*100)) - int(cents.sum())
    while remainder:
        sign = 1 if remainder > 0 else -1
        eligible = np.where(cents < upper if sign > 0 else cents > lower)[0]
        if not len(eligible):
            raise ValueError("Budget cannot be rounded within the change limits.")
        best = eligible[np.argmax(sign*(scaled[eligible]-cents[eligible]))]
        cents[best] += sign
        remainder -= sign
    return cents/100.


def load():
    p = pd.read_csv(OUT / "predictions.csv", parse_dates=["data"])
    p["cpc_pred"] = p.cpm_pred / (10 * p.ctr_pred)
    return p


def daily_budget_plan(p):
    """Equal spend across active ads, then concave optimization within +/-20%.

    Equal allocation is explicit because future platform delivery shares are unknown.
    The pessimistic sensitivity charges removed spend at favourable KPI bounds and
    added spend at adverse bounds; it is not a calibrated confidence interval.
    """
    p = p.copy()
    p["efficiency"] = 10 * p.ctr_pred / p.cpm_pred
    p["eff_low"] = 10 * p.ctr_lo / p.cpm_hi
    p["eff_high"] = 10 * p.ctr_hi / p.cpm_lo
    rows = []
    for (day, campaign), group in p.groupby(["data", "campaign_id"], observed=True):
        sets = group.groupby("adset_id", observed=True).agg(budget=("budget_giornaliero_adset", "first"),
            efficiency=("efficiency", "mean"), eff_low=("eff_low", "mean"), eff_high=("eff_high", "mean"),
            ctr=("ctr_pred", "mean"), cpm=("cpm_pred", "mean"), ads=("ad_id", "nunique")).reset_index()
        b = sets.budget.to_numpy(float)
        c = b * sets.efficiency.to_numpy(float)
        result = minimize(lambda x: -np.sum(c * (x / b) ** ELASTICITY), b,
                          method="SLSQP", bounds=list(zip(b*(1-MAX_CHANGE), b*(1+MAX_CHANGE))),
                          constraints={"type": "eq", "fun": lambda x: x.sum() - b.sum()},
                          options={"ftol": 1e-10, "maxiter": 300})
        new = result.x if result.success else b.copy()
        new = round_budget(new, b)
        if not np.isclose(new.sum(), b.sum(), atol=1e-5):
            raise ValueError("Budget optimization failed conservation.")
        ratios = new / b
        gains = [float(np.sum(c * (ratios**e-1))) for e in ELASTICITY_RANGE]
        downside = []
        for e in ELASTICITY_RANGE:
            change = ratios**e - 1
            efficiency = np.where(change >= 0, sets.eff_low, sets.eff_high)
            downside.append(float(np.sum(b * efficiency * change)))
        sets["data"], sets["campaign_id"] = day, campaign
        sets["cpc"] = 1 / sets.efficiency
        sets["clicks_per_day"] = c
        sets["budget_proposed"] = new
        sets["clicks_per_day_proposed"] = c * ratios**ELASTICITY
        sets["campaign_gain_clicks_per_day"] = np.sum(c * (ratios**ELASTICITY-1))
        sets["gain_elasticity_min"], sets["gain_elasticity_max"] = min(gains), max(gains)
        sets["gain_adverse_kpi_min"] = min(downside)
        sets["note"] = "Scenario only: test gradually; KPI uncertainty can erase the gain."
        sets["solver_success"] = result.success
        rows.append(sets)
    return pd.concat(rows, ignore_index=True)


def budget_plan(p):
    daily = daily_budget_plan(p)
    nums = ["budget", "ctr", "cpm", "cpc", "clicks_per_day", "budget_proposed", "clicks_per_day_proposed",
            "campaign_gain_clicks_per_day", "gain_elasticity_min", "gain_elasticity_max", "gain_adverse_kpi_min"]
    out = daily.groupby(["campaign_id", "adset_id"])[nums].mean().reset_index()
    out["note"] = "Daily scenario averaged here; equal spend across active ads; not sales uplift."
    return out.round(4)


def _by_week(p):
    p = p.copy()
    p["week"] = ""
    for name, (a, b) in WEEKS.items():
        p.loc[p.data.between(a, b), "week"] = name
    return p[p.week != ""]


def creative_plan(p):
    rows = []
    for (adset, week), group in _by_week(p).groupby(["adset_id", "week"], observed=True):
        counts = group.groupby("data").ad_id.nunique()
        # Compare every candidate over the same dates, avoiding launch-date bias.
        dates = counts[counts == group.ad_id.nunique()].index
        if not len(dates):
            continue
        group = group[group.data.isin(dates)]
        per_ad = group.groupby(["ad_id", "asset_id", "leva", "formato"], observed=True).agg(
            ctr=("ctr_pred", "mean"), lo=("ctr_lo", "min"), hi=("ctr_hi", "max"),
            cpm=("cpm_pred", "mean"), cold=("cold_start", "max")).reset_index().sort_values("ctr", ascending=False)
        top, bottom = per_ad.iloc[0], per_ad.iloc[-1]
        separated = bool(top.lo > bottom.hi)
        rows.append(dict(adset_id=adset, week=week, comparison_days=len(dates),
            comparison_start=str(dates.min().date()), comparison_end=str(dates.max().date()),
            push=top.ad_id, push_asset=top.asset_id, push_leva=top.leva, push_formato=top.formato,
            push_ctr=round(top.ctr, 3), push_band=f"{top.lo:.2f}-{top.hi:.2f}", push_is_cold_start=bool(top.cold),
            pause=bottom.ad_id, pause_asset=bottom.asset_id, pause_ctr=round(bottom.ctr, 3),
            ctr_gap=f"{top.ctr/bottom.ctr:.1f}x", daily_envelopes_separate=separated,
            action="Prioritise winner; consider pausing weakest" if separated else "Test challenger; overlapping uncertainty"))
    return pd.DataFrame(rows)


def timing(p):
    d = p.groupby("data").agg(ctr=("ctr_pred", "mean"), cpm=("cpm_pred", "mean"), cpc=("cpc_pred", "mean")).round(3)
    d["cpm_vs_first_day"] = (d.cpm / d.cpm.iloc[0]).round(2)
    return d


def main():
    OUT.mkdir(exist_ok=True)
    p = load()
    b, c, t = budget_plan(p), creative_plan(p), timing(p)
    daily_budget_plan(p).round(6).to_csv(OUT / "decisions_budget_daily.csv", index=False)
    b.to_csv(OUT / "decisions_budget.csv", index=False)
    c.to_csv(OUT / "decisions_creative.csv", index=False)
    t.to_csv(OUT / "decisions_timing.csv")
    assumption = ("Click allocation scenarios, not causal or sales predictions. Future ad delivery is assumed equal within each ad set/day. "
                  "Optimisation preserves each campaign/day budget and caps every set's change at 20%. "
                  "Elasticity 0.42 is an assumption; sensitivity covers 0.25-1.0. "
                  "Daily prediction bounds are not confidence intervals for average CTR or winning probability.")
    lines = ["# Decisions for 16-30 November\n", assumption, "\n## Budget scenarios\n", b.to_markdown(index=False),
             "\n## Creative comparisons on common dates\n", c.to_markdown(index=False),
             "\n## Timing (unweighted descriptive averages)\n", t.to_markdown()]
    (OUT / "decisions.md").write_text("\n".join(lines), encoding="utf-8")
    payload = {"assumptions": assumption, "budget": b.to_dict("records"), "creative": c.to_dict("records"),
               "timing": t.reset_index().assign(data=lambda d:d.data.dt.strftime("%Y-%m-%d")).to_dict("records")}
    (OUT / "decisions.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(b[["adset_id", "budget", "budget_proposed", "campaign_gain_clicks_per_day", "gain_adverse_kpi_min"]].to_string(index=False))


if __name__ == "__main__":
    main()
