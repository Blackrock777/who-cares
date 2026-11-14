"""Infer who is behind each ad set from its behaviour, and write the audience hypotheses.

The organisers hide the audiences. We reverse-engineer them from a behavioural fingerprint:
cost per reach, frequency, fatigue speed, response to levers and to creative features.

Writes out/audiences.md (for the README) and out/audiences.json (for the app).
"""
import json
from pathlib import Path

import pandas as pd

from features import load_history

OUT = Path(__file__).resolve().parents[1] / "out"

# One hypothesis per ad-set rank. The same structure repeats in all three advertisers,
# which is itself evidence: it is how a Meta account for a sales campaign is usually built.
HYPOTHESES = {
    "1": {
        "name": "Broad prospecting (cold)",
        "who": "Everyone 18-65 in Italy, no interest targeting (Advantage+ broad). The widest and "
               "cheapest audience in the account, mostly people who have never heard of the brand.",
        "evidence": [
            "Largest budget and the lowest CPM in every advertiser: Meta finds cheap impressions because the pool is huge.",
            "Highest reach per euro and frequency pinned at 1.03: almost nobody sees an ad twice.",
            "Lowest CTR: a cold stranger rarely clicks.",
            "Almost no fatigue (week-4 CTR is 92-97% of week-0): the pool refreshes itself.",
            "Black Friday lever under-indexes (0.8-0.9x): a cold audience is not waiting for this brand's sale.",
        ],
        "implication": "Use it for reach and for creative that explains the product. Keep heavy-text graphics out: this is where they hurt most.",
    },
    "2": {
        "name": "Interest / lookalike, deal-driven, younger",
        "who": "Interest-based or 1-3% lookalike of past buyers, skewed 25-34, Instagram-heavy, "
               "responds to deals and to people on camera.",
        "evidence": [
            "Mid budget, CPM 10-20% above ad set 1: a narrower pool, but still cold (frequency 1.03).",
            "Fastest fatigue after the warm set (week-4 CTR is ~70% of week-0): the pool is finite.",
            "Black Friday lever over-indexes strongly (1.2-1.7x) and scarcity over-indexes: deal hunters.",
            "Weekend CTR slightly higher (Saturday +6%): leisure browsing, not desk browsing.",
            "Video and talking-to-camera creatives beat images by 1.3-1.7x.",
        ],
        "implication": "The right place for promo creatives in Black Week. Rotate creatives every 3-4 weeks; it burns out.",
    },
    "3": {
        "name": "Narrow premium interest, older",
        "who": "Tight interest stack (premium skincare / premium pet food / mid-range fashion), "
               "skewed 35-54, higher income, trust-driven rather than deal-driven.",
        "evidence": [
            "Smallest budget yet CPM close to the warm set: an expensive, narrow pool.",
            "Frequency 1.035, slightly above the other cold sets: a smaller pool reached more than once.",
            "Black Friday lever under-indexes most (0.6-0.7x): price is not what moves them.",
            "Scarcity creatives over-index and 'talking to camera' creatives get the biggest lift of any set (1.4x).",
            "Almost no fatigue (0.9-1.0): a loyal, stable segment that tolerates the same creative.",
        ],
        "implication": "Sell quality and proof, not discounts. The dermatologist video and the numbered-kit carousel belong here.",
    },
    "4": {
        "name": "Retargeting (warm)",
        "who": "Site visitors, add-to-cart and past customers of the last 30-90 days. People who already "
               "know the brand and are deciding whether to buy.",
        "evidence": [
            "CTR about 2x the cold sets in every advertiser: warm people click.",
            "Frequency 1.20-1.24 against 1.03 elsewhere: a small pool, so the same people see the ad again.",
            "Lowest reach per euro and the highest CPM: competition for warm users is expensive and the pool is small.",
            "Strongest fatigue of all (week-4 CTR is 60-72% of week-0): once the pool has seen it, it is done.",
            "Black Friday lever over-indexes 1.35-1.6x and Friday-to-Sunday CTR is above average: they were waiting for the price drop.",
        ],
        "implication": "Highest click volume per euro. Load Black Friday creatives here first, refresh weekly, and cap frequency.",
    },
}


def fingerprint() -> pd.DataFrame:
    h = load_history()
    h["cpc"] = h["spesa"] / h["click"]
    h["reach_per_eur"] = h["copertura"] / h["spesa"]
    g = h.groupby("adset_id", observed=True)
    wk0 = h[h["days_since_launch"] < 7].groupby("adset_id", observed=True)["ctr"].mean()
    wk4 = h[h["days_since_launch"] >= 28].groupby("adset_id", observed=True)["ctr"].mean()
    bf = h[h["leva"] == "black_friday"].groupby("adset_id", observed=True)["ctr"].mean()
    tab = pd.DataFrame({
        "budget_eur": g["budget"].mean(),
        "ctr_%": g["ctr"].mean(),
        "cpm_eur": g["cpm"].mean(),
        "cpc_eur": g["cpc"].mean(),
        "frequency": g["frequenza"].mean(),
        "reach_per_eur": g["reach_per_eur"].mean(),
        "fatigue_wk4_vs_wk0": wk4 / wk0,
        "black_friday_lift": bf / g["ctr"].mean(),
    }).round(3)
    tab["rank"] = tab.index.str[-1]
    tab["audience"] = tab["rank"].map({k: v["name"] for k, v in HYPOTHESES.items()})
    return tab


def main():
    OUT.mkdir(exist_ok=True)
    tab = fingerprint()
    tab.to_csv(OUT / "adset_fingerprint.csv")
    lines = ["# Who is behind each ad set\n",
             "The audiences are hidden, so we inferred them from behaviour. The same four-way structure "
             "appears in all three advertisers, which is the standard way a Meta sales campaign is built: "
             "one broad set, two interest sets, one retargeting set.\n",
             "## Fingerprint (history, traps removed)\n", tab.to_markdown(), ""]
    for rank, hyp in HYPOTHESES.items():
        sets = ", ".join(tab.index[tab["rank"] == rank])
        lines += [f"## Ad set {rank} ({sets}): {hyp['name']}\n", f"**Who:** {hyp['who']}\n", "**Evidence:**"]
        lines += [f"- {e}" for e in hyp["evidence"]]
        lines += ["", f"**What it means for the plan:** {hyp['implication']}", ""]
    (OUT / "audiences.md").write_text("\n".join(lines), encoding="utf-8")
    payload = {row: {**HYPOTHESES[row[-1]], "fingerprint": tab.loc[row].drop(["rank", "audience"]).to_dict()}
               for row in tab.index}
    (OUT / "audiences.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tab.to_string())


if __name__ == "__main__":
    main()
