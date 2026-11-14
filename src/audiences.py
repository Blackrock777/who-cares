"""Infer behavioural audience hypotheses from each ad set's measured fingerprint.

Identities, ages, income and targeting settings are not observed in this kit.
A warm-response profile is consistent with retargeting, not proof of it.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from features import load_history

OUT = Path(__file__).resolve().parents[1] / "out"
PROFILES = {
    "broad": {
        "name": "Broad / discovery response",
        "who": "A broad, relatively cold audience is plausible. Low auction cost and weak click response support this reading.",
        "implication": "Test a clear product introduction against the strongest existing creative.",
        "alternative": "Cheap placements or weaker creative delivery could produce a similar profile.",
    },
    "deal": {
        "name": "Promotion-responsive prospecting hypothesis",
        "who": "An interest or lookalike prospecting audience is plausible. Promotion response should be tested rather than assumed.",
        "implication": "Compare promotion, scarcity and urgency on the same dates. Watch the measured creative fatigue.",
        "alternative": "Creative mix and launch dates can explain apparent deal sensitivity.",
    },
    "selective": {
        "name": "Selective / higher-cost response",
        "who": "A narrower or more expensive audience is plausible. Premium interests and trust needs are hypotheses only.",
        "implication": "Compare product proof with discount-led creative; retain the winner only when the evidence supports it.",
        "alternative": "Placement, bidding or competition can raise CPM without premium customers.",
    },
    "warm": {
        "name": "Warm-response / retargeting hypothesis",
        "who": "Visitors, previous buyers or cart abandoners are plausible: repeat exposure and click propensity are relatively high.",
        "implication": "Prioritise promising creatives cautiously and monitor fatigue; high CTR does not establish sales lift.",
        "alternative": "A small, highly interested prospecting pool can also click often and see repeated impressions.",
    },
    "uncertain": {
        "name": "Mixed prospecting response / identity uncertain",
        "who": "An interest-based audience is plausible, but the observed signals do not reliably distinguish deal seekers from selective shoppers.",
        "implication": "Run a controlled proof-versus-promotion comparison before changing the targeting story.",
        "alternative": "Creative mix, delivery and time effects can explain the differences between these ad sets.",
    },
}


def fingerprint(history=None):
    h = load_history() if history is None else history.copy()
    g = h.groupby("adset_id", observed=True)
    tab = g.agg(budget_eur=("budget", "mean"), impressions=("impression", "sum"),
                clicks=("click", "sum"), spend=("spesa", "sum"),
                frequency=("frequenza", "median"), rows=("ad_id", "size"))
    tab["ctr_%"] = tab.clicks / tab.impressions * 100
    tab["cpm_eur"] = tab.spend / tab.impressions * 1000
    tab["cpc_eur"] = tab.spend / tab.clicks
    tab["reach_per_eur"] = g["copertura"].sum() / tab.spend
    # Compare the SAME ad's first observed week with observations 28+ days later.
    # Remove the supplied seasonal CTR index first. This is descriptive, not causal.
    h["observed_age"] = (h.data - h.groupby("ad_id", observed=True).data.transform("min")).dt.days
    h["normalized_ctr"] = h.ctr / (h.idx_ctr / 100)
    early = h[h.observed_age < 7].groupby(["adset_id", "ad_id"], observed=True).normalized_ctr.mean()
    late = h[h.observed_age >= 28].groupby(["adset_id", "ad_id"], observed=True).normalized_ctr.mean()
    ratios = (late / early).dropna()
    tab["fatigue_late_vs_first_week"] = ratios.groupby(level=0, observed=True).median()
    tab["fatigue_ads"] = ratios.groupby(level=0, observed=True).size()
    bf = h[h.leva == "black_friday"].groupby("adset_id", observed=True).ctr.mean()
    tab["bf_mix_ratio"] = bf / g.ctr.mean()
    # Asset/date matching reduces (but does not eliminate) creative-mix confounding.
    match = h.groupby(["data", "asset_id"], observed=True).ctr.transform("mean")
    nsets = h.groupby(["data", "asset_id"], observed=True).adset_id.transform("nunique")
    h["matched_ctr_ratio"] = (h.ctr / match).where(nsets > 1)
    tab["matched_ctr_ratio"] = h.groupby("adset_id", observed=True).matched_ctr_ratio.median()
    tab["campaign_id"] = g.campaign_id.first()
    tab["profile"] = ""
    # Explicit heuristic hypotheses. Do not force one of every type per advertiser.
    # These thresholds describe relative behaviour, not recovered targeting settings.
    for _, group in tab.groupby("campaign_id"):
        tab.loc[group.index, "profile"] = "uncertain"
        for adset, row in group.iterrows():
            if row.frequency > 1.1*group.frequency.median() and row['ctr_%'] > group['ctr_%'].median():
                key = "warm"
            elif row.cpm_eur == group.cpm_eur.min() and row['ctr_%'] < group['ctr_%'].median():
                key = "broad"
            elif row.bf_mix_ratio > 1.1 and row.fatigue_late_vs_first_week < .8:
                key = "deal"
            elif row.cpm_eur > 1.1*group.cpm_eur.median() and row.bf_mix_ratio < 1:
                key = "selective"
            else:
                key = "uncertain"
            tab.loc[adset, "profile"] = key
    tab["audience"] = tab.profile.map(lambda x: PROFILES[x]["name"])
    return tab.round(4)


def infer(history=None):
    tab = fingerprint(history)
    payload = {}
    for adset, row in tab.iterrows():
        profile = PROFILES[row.profile]
        evidence = [f"{int(row.rows)} cleaned ad-day observations; pooled CTR {row['ctr_%']:.2f}%, CPM €{row.cpm_eur:.2f}.",
                    f"Median daily frequency per ad {row.frequency:.3f}; this is not deduplicated audience reach.",
                    f"Within-ad late/first-week CTR ratio, season-adjusted: {row.fatigue_late_vs_first_week:.2f} across {int(row.fatigue_ads)} ads.",
                    f"Same-asset/day relative CTR median {row.matched_ctr_ratio:.2f}; a descriptive matched comparison.",
                    f"Black Friday creative CTR / all-creative CTR {row.bf_mix_ratio:.2f}; creative/date mix confounds this comparison."]
        values = row.drop(["campaign_id", "profile", "audience"]).to_dict()
        values = {k: (None if pd.isna(v) else v) for k, v in values.items()}
        payload[str(adset)] = {**profile, "profile": row.profile, "evidence": evidence,
                              "confidence": "Moderate for relative behaviour; low for targeting identity; demographics unobserved.",
                              "demographics": "Age, gender, income, geography and placement cannot be recovered from these aggregates.",
                              "fingerprint": values}
    return tab, payload


def main():
    OUT.mkdir(exist_ok=True)
    tab, payload = infer()
    tab.to_csv(OUT / "adset_fingerprint.csv")
    lines = ["# Audience hypotheses grounded in observed response\n",
             "Simulated challenge data. Targeting identities and demographics are not observed. "
             "Profiles are ranked from metrics within each advertiser, not assigned from ad-set IDs.\n",
             tab.to_markdown(), ""]
    for adset, hyp in payload.items():
        lines += [f"## {adset}: {hyp['name']}\n", hyp["who"], "",
                  f"**Confidence:** {hyp['confidence']}", f"**Unobserved:** {hyp['demographics']}", "",
                  *[f"- {e}" for e in hyp["evidence"]], "",
                  f"**Alternative:** {hyp['alternative']}", f"**Decision:** {hyp['implication']}", ""]
    (OUT / "audiences.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "audiences.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(tab[["audience", "ctr_%", "cpm_eur", "frequency", "fatigue_late_vs_first_week"]].to_string())


if __name__ == "__main__":
    main()
