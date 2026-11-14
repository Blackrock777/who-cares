"""Turn the predictions into decisions: where the budget should go, which creative and
lever to run in each ad set, and when.

Reads out/predictions.csv. Writes out/decisions.md and out/decisions.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "out"

# Measured in the history when NDL ad set 4 went from 45 to 90 euro/day:
# CPM +28%, CTR -14%. Clicks therefore scale with budget^ELASTICITY, not linearly.
ELASTICITY = 0.42
WEEKS = {"Pre Black Week (16-22 Nov)": ("2026-11-16", "2026-11-22"),
         "Black Week + Black Friday (23-30 Nov)": ("2026-11-23", "2026-11-30")}


def load():
    p = pd.read_csv(OUT / "predictions.csv", parse_dates=["data"])
    p["cpc_pred"] = p["cpm_pred"] / (10 * p["ctr_pred"])          # euro per click
    p["clicks_per_100eur"] = 100 / p["cpc_pred"]
    return p


def budget_plan(p):
    """Per ad set: expected cost per click, and a reallocation that moves budget from the
    most expensive clicks to the cheapest, with diminishing returns."""
    rows = []
    for camp, grp in p.groupby("campaign_id"):
        by_set = grp.groupby("adset_id").agg(budget=("budget_giornaliero_adset", "mean"),
                                             ctr=("ctr_pred", "mean"), cpm=("cpm_pred", "mean"),
                                             cpc=("cpc_pred", "mean")).reset_index()
        by_set["clicks_per_day"] = by_set["budget"] / by_set["cpc"]
        total = by_set["budget"].sum()
        # move 20% of the worst set's budget to the best set, apply elasticity to both
        best, worst = by_set["cpc"].idxmin(), by_set["cpc"].idxmax()
        move = 0.2 * by_set.loc[worst, "budget"]
        new = by_set["budget"].copy()
        new[worst] -= move
        new[best] += move
        ratio = new / by_set["budget"]
        new_clicks = by_set["clicks_per_day"] * ratio ** ELASTICITY
        by_set["budget_proposed"] = new.round(0)
        by_set["clicks_per_day_proposed"] = new_clicks.round(1)
        by_set["campaign_id"] = camp
        gain = new_clicks.sum() - by_set["clicks_per_day"].sum()
        by_set["campaign_gain_clicks_per_day"] = round(gain, 1)
        by_set["note"] = ""
        by_set.loc[best, "note"] = "cheapest clicks: receives the shift"
        by_set.loc[worst, "note"] = "most expensive clicks: gives 20% of budget"
        rows.append(by_set)
    out = pd.concat(rows, ignore_index=True)
    out["total_budget"] = out.groupby("campaign_id")["budget"].transform("sum")
    assert np.allclose(out.groupby("campaign_id")["budget_proposed"].sum(), out.groupby("campaign_id")["budget"].sum(), atol=1)
    return out.round(3)


def creative_plan(p):
    """Per ad set and week: the creative to push, the one to pause, with reasons."""
    rows = []
    for (adset, week), grp in _by_week(p).groupby(["adset_id", "week"]):
        per_ad = grp.groupby(["ad_id", "asset_id", "leva", "formato"]).agg(
            ctr=("ctr_pred", "mean"), lo=("ctr_lo", "mean"), hi=("ctr_hi", "mean"),
            cpm=("cpm_pred", "mean"), cold=("cold_start", "max")).reset_index().sort_values("ctr", ascending=False)
        top, bottom = per_ad.iloc[0], per_ad.iloc[-1]
        gap = top["ctr"] / bottom["ctr"]
        rows.append(dict(adset_id=adset, week=week,
                         push=top["ad_id"], push_asset=top["asset_id"], push_leva=top["leva"], push_formato=top["formato"],
                         push_ctr=round(top["ctr"], 2), push_band=f"{top['lo']:.2f}-{top['hi']:.2f}",
                         push_is_cold_start=bool(top["cold"]),
                         pause=bottom["ad_id"], pause_asset=bottom["asset_id"], pause_ctr=round(bottom["ctr"], 2),
                         ctr_gap=f"{gap:.1f}x",
                         confident=bool(top["lo"] > bottom["hi"])))
    return pd.DataFrame(rows)


def _by_week(p):
    p = p.copy()
    p["week"] = ""
    for name, (a, b) in WEEKS.items():
        p.loc[(p["data"] >= a) & (p["data"] <= b), "week"] = name
    return p


def timing(p):
    """How much the market moves day by day, from the model."""
    d = p.groupby("data").agg(ctr=("ctr_pred", "mean"), cpm=("cpm_pred", "mean"), cpc=("cpc_pred", "mean")).round(3)
    d["cpm_vs_first_day"] = (d["cpm"] / d["cpm"].iloc[0]).round(2)
    return d


def main():
    p = load()
    b, c, t = budget_plan(p), creative_plan(p), timing(p)
    b.to_csv(OUT / "decisions_budget.csv", index=False)
    c.to_csv(OUT / "decisions_creative.csv", index=False)
    t.to_csv(OUT / "decisions_timing.csv")
    lines = ["# Decisions for 16-30 November\n",
             "## Budget: where a euro buys the most clicks\n",
             "Cost per click = CPM / (10 x CTR). Clicks scale with budget^0.42 (measured in the history "
             "when an ad set doubled its budget: CPM +28%, CTR -14%).\n",
             b[["campaign_id", "adset_id", "budget", "ctr", "cpm", "cpc", "clicks_per_day", "budget_proposed",
                "clicks_per_day_proposed", "note"]].to_markdown(index=False), "",
             "## Creative and lever: push and pause, per ad set and week\n",
             c.to_markdown(index=False), "",
             "## Timing: the market day by day\n", t.to_markdown(), ""]
    (OUT / "decisions.md").write_text("\n".join(lines), encoding="utf-8")
    json.dump({"budget": b.to_dict("records"), "creative": c.to_dict("records"),
               "timing": t.reset_index().assign(data=lambda d: d["data"].dt.strftime("%Y-%m-%d")).to_dict("records")},
              open(OUT / "decisions.json", "w"), indent=2, ensure_ascii=False, default=float)
    print(b[["campaign_id", "adset_id", "budget", "cpc", "clicks_per_day", "budget_proposed", "clicks_per_day_proposed", "note"]].to_string(index=False))
    print()
    print(c[["adset_id", "week", "push", "push_ctr", "push_band", "pause", "pause_ctr", "ctr_gap", "confident"]].to_string(index=False))


if __name__ == "__main__":
    main()
