"""Build data/priors/priors.json: every number the audience model and the world simulator use,
each with the source it came from. Re-run after refreshing any source.

Sources (details and caveats in docs/SOURCES.md):
  population      Meta Marketing API audience estimate, Italy, broad 18+ (Affectgroup, Mar 2026)
  vertical mixes  Meta Ad Library (EU DSA transparency): reach by age x gender of real Italian ads,
                  pulled with scripts/fetch_apify_ads.py (Sephora = beauty, Arcaplanet = pet, OVS = apparel)
  cell effects    Kaggle "Sales conversion optimisation" Facebook ads (1,143 ads, age 30-49, M/F):
                  Poisson GLM on clicks with impressions as exposure, campaign + interest fixed effects,
                  campaign-cluster bootstrap. CPM gender ratio cross-checked against Lebesgue (2025).
  vertical CTR    WordStream / LocaliQ Facebook ads benchmarks 2025 (traffic campaigns)
  CPM level       organisers' kit, cpm_storici.csv (Meta, Italy, sales objective, monthly median + IQR)
  season          organisers' kit, 2025 weekly market index; BF lift cross-checked against Lebesgue
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor, Ridge

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
AGES = ["18-24", "25-34", "35-44", "45-54", "55+"]
GENDERS = ["F", "M"]
CENTRE = {"18-24": 21.0, "25-34": 29.5, "35-44": 39.5, "45-54": 49.5, "55+": 62.0}
KAGGLE_AGE_RANGE = (30.0, 49.0)
REF_AGE = 32.0

# Meta Marketing API, Italy, broad 18+, accounts (millions). Affectgroup, published 2026-03-01.
POPULATION = {("18-24", "F"): 2.9, ("18-24", "M"): 2.6, ("25-34", "F"): 4.3, ("25-34", "M"): 4.8,
              ("35-44", "F"): 3.3, ("35-44", "M"): 3.4, ("45-54", "F"): 3.6, ("45-54", "M"): 3.3,
              ("55+", "F"): 5.8, ("55+", "M"): 5.4}

VERTICAL_SOURCES = {"beauty_skincare": ("sephora", "Sephora Italia / France", None),
                    "pet_ecommerce": ("arcaplanet", "Arcaplanet", "Arcaplanet"),
                    "abbigliamento": ("ovs", "OVS", "OVS")}           # exact page: the keyword also matched JOVS, OVS Kids, Swarovski

# WordStream / LocaliQ 2025, Facebook traffic campaigns. Used as relative vertical levels only.
WORDSTREAM_CTR = {"beauty_skincare": 1.81, "pet_ecommerce": 1.64, "abbigliamento": 1.29}


def cells():
    return [f"{g}|{a}" for g in GENDERS for a in AGES]


def age_band(raw):
    raw = str(raw)
    return {"55-64": "55+", "65+": "55+"}.get(raw, raw)


def vertical_mix(name, page=None):
    """Reach share by cell for one brand's Italian ads, plus the Dirichlet concentration implied by
    how much individual ads differ (method of moments: Var(w_c) = m_c (1 - m_c) / (kappa + 1))."""
    f = ROOT / "data" / "external" / "ad_library" / name / "reach_by_demographic.csv"
    if not f.exists():
        return None
    r = pd.read_csv(f)
    if page:
        a = pd.read_csv(f.parent / "ads.csv", usecols=["ad_id", "page_name"])
        r = r[r["ad_id"].isin(a.loc[a["page_name"] == page, "ad_id"])]
    it = r[r["country"] == "IT"]
    r = it if it["ad_id"].nunique() >= 20 else r                       # fall back to all EU rows if Italy is thin
    r = r[r["gender"].isin(["female", "male"]) & r["age"].map(age_band).isin(AGES)].copy()
    r["cell"] = r["gender"].str[0].str.upper() + "|" + r["age"].map(age_band)
    w = r.pivot_table(index="ad_id", columns="cell", values="reach", aggfunc="sum").reindex(columns=cells()).fillna(0)
    w = w[w.sum(1) > 0]
    tot = w.sum(1)
    shares = w.div(tot, axis=0)
    mean = (w.sum() / w.values.sum()).values                             # reach-weighted mean mix
    big = shares[tot >= tot.quantile(0.25)]                              # tiny ads are noisy shares
    var = big.var().values
    kappa = float(np.median((mean * (1 - mean))[mean > 0.02] / np.maximum(var[mean > 0.02], 1e-6) - 1))
    return {"mean": dict(zip(cells(), mean.round(5))), "kappa": round(max(kappa, 1.0), 2), "n_ads": int(len(w)),
            "countries": sorted(r["country"].unique().tolist()), "total_reach": float(w.values.sum())}


def kaggle_effects(boot=200):
    d = pd.read_csv(ROOT / "data" / "external" / "kaggle_sales_conversion" / "KAG_conversion_data.csv")
    d = d[d["Impressions"] > 0]
    d["age_c"] = d["age"].str[:2].astype(float) + 2.0                   # 30-34 -> 32
    cols = ["gender", "xyz_campaign_id", "interest"]

    def fit(dd):
        X = pd.get_dummies(dd[cols].astype(str)).astype(float)
        X["age5"] = (dd["age_c"].values - REF_AGE) / 5
        ctr = PoissonRegressor(alpha=1e-4, max_iter=5000).fit(X, dd["Clicks"] / dd["Impressions"] * 1e4,
                                                              sample_weight=dd["Impressions"] / dd["Impressions"].mean())
        c = pd.Series(ctr.coef_, X.columns)
        s = dd["Spent"] > 0
        cpm = Ridge(alpha=1e-3).fit(X[s.values], np.log(dd.loc[s, "Spent"] / dd.loc[s, "Impressions"] * 1000),
                                    sample_weight=dd.loc[s, "Impressions"])
        p = pd.Series(cpm.coef_, X.columns)
        return [c["gender_F"] - c["gender_M"], c["age5"], p["gender_F"] - p["gender_M"], p["age5"]]

    est = np.array(fit(d))
    rng, camps, res = np.random.default_rng(0), d["fb_campaign_id"].unique(), []
    for _ in range(boot):
        bd = pd.concat([d[d["fb_campaign_id"] == c] for c in rng.choice(camps, len(camps))])
        if bd["gender"].nunique() == 2 and bd["age"].nunique() >= 3:
            res.append(fit(bd))
    sd = np.array(res).std(0)
    names = ["ctr_log_female", "ctr_log_per_5y", "cpm_log_female", "cpm_log_per_5y"]
    return {n: {"estimate": round(float(e), 4), "bootstrap_sd": round(float(s), 4)} for n, e, s in zip(names, est, sd)}, len(d)


def cell_multipliers(eff, external_sd=0.10, extrap_shrink=0.5, extrap_sd_per_decade=0.15):
    """log multiplier and its uncertainty per cell, for CTR and CPM.

    Inside the observed age range the Kaggle slope is used as is. Beyond it the slope is halved
    (we do not assume a straight line continues) and the uncertainty grows per decade of
    extrapolation. `external_sd` is added everywhere: one dataset of unverified provenance."""
    out = {}
    for kpi in ("ctr", "cpm"):
        g, a = eff[f"{kpi}_log_female"], eff[f"{kpi}_log_per_5y"]
        m, s = {}, {}
        for cell in cells():
            gen, band = cell.split("|")
            x = CENTRE[band]
            lo, hi = KAGGLE_AGE_RANGE
            inside = min(max(x, lo), hi)
            outside = x - inside
            dist5 = (inside - REF_AGE) / 5 + extrap_shrink * outside / 5
            mu = (g["estimate"] if gen == "F" else 0.0) + a["estimate"] * dist5
            var = external_sd ** 2 + (g["bootstrap_sd"] ** 2 if gen == "F" else 0) + (a["bootstrap_sd"] * dist5) ** 2 \
                + (extrap_sd_per_decade * abs(outside) / 10) ** 2
            m[cell], s[cell] = mu, var ** 0.5
        pop = np.array([POPULATION[(c.split("|")[1], c.split("|")[0])] for c in cells()])
        centre = np.log(np.sum(pop / pop.sum() * np.exp(np.array([m[c] for c in cells()]))))
        out[kpi] = {"log_mult": {c: round(m[c] - centre, 4) for c in cells()}, "log_sd": {c: round(s[c], 4) for c in cells()}}
    return out


def main():
    pop = np.array([POPULATION[(c.split("|")[1], c.split("|")[0])] for c in cells()])
    eff, n_kaggle = kaggle_effects()
    verticals = {}
    for v, (folder, label, page) in VERTICAL_SOURCES.items():
        mix = vertical_mix(folder, page)
        if mix is None:
            mix = {"mean": dict(zip(cells(), (pop / pop.sum()).round(5))), "kappa": 8.0, "n_ads": 0, "countries": [],
                   "fallback": "no Ad Library pull found; Italian Meta population used"}
        mix["source_brand"] = label
        mix["wordstream_ctr_2025"] = WORDSTREAM_CTR[v]
        verticals[v] = mix
    cpm = pd.read_csv(ROOT / "data" / "raw" / "cpm_storici.csv")
    cpm = cpm[(cpm.piattaforma == "meta") & (cpm.paese == "IT") & (cpm.obiettivo == "vendite")]
    b = pd.read_csv(ROOT / "data" / "raw" / "benchmark_mercato_settimanale_2025.csv", parse_dates=["settimana_dal"])
    bf = {v: round(float(g.loc[g.settimana_dal == "2025-11-24", "indice_cpm"].iloc[0] / g.loc[g.settimana_dal.dt.month == 9, "indice_cpm"].mean()), 3)
          for v, g in b.groupby("vertical")}
    pri = {
        "cells": cells(), "ages": AGES, "genders": GENDERS, "age_centre": CENTRE,
        "population_it_millions": dict(zip(cells(), pop.round(2).tolist())),
        "verticals": verticals,
        "kaggle_effects": eff, "kaggle_rows": n_kaggle,
        "cell_effects": cell_multipliers(eff),
        "cpm_it_sales_monthly": cpm[["mese", "cpm_mediano", "cpm_q1", "cpm_q3", "n_campagne"]].to_dict("records"),
        "bf_week_cpm_vs_september": {"kit_2025_index": bf, "lebesgue_2024": 1.80, "lebesgue_2025": 1.59, "nest_commerce_bf_day_yoy_2024": 1.21},
        "cross_checks": {"cpm_female_over_male": {"kaggle_adjusted": round(float(np.exp(eff["cpm_log_female"]["estimate"])), 3),
                                                   "lebesgue_2025": round(6.01 / 4.92, 3)}},
        "warm": {
            "prior_probability": 0.2,
            "ctr_log_effect": {"mean": 0.0, "sd": 0.5, "source": "Lebesgue: retargeting CTR ~1.0% vs prospecting ~1.34%; Coinis: retargeting CTR higher. Sources disagree, so centred on no effect with a wide spread."},
            "cpm_log_effect": {"mean": round(float(np.log(1.8)), 4), "sd": 0.35, "source": "Lebesgue 2022-23: retargeting CPM >100% above prospecting (~$13 vs ~$6-8). Centred on +80%, wide."},
            "log_frequency_excess": {"cold": {"mean": 0.0, "sd": 0.04}, "warm": {"mean": 0.15, "sd": 0.10},
                                     "source": "assumption: a retargeting pool is small, so the same budget reaches the same people more often. Tested on simulated companies, not on real data."}},
        "assumptions": {"external_sd": 0.10, "extrapolation_slope_shrink": 0.5, "extrapolation_sd_per_decade": 0.15,
                        "targeting_noise_log_sd": {"ctr": 0.15, "cpm": 0.10}},
    }
    out = ROOT / "data" / "priors" / "priors.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pri, indent=1))
    print("wrote", out)
    for v, m in verticals.items():
        f = sum(x for c, x in m["mean"].items() if c.startswith("F"))
        print(f"  {v:16s} ads={m['n_ads']:5d} kappa={m['kappa']:6.2f} female={f:.2f} {m.get('fallback', '')}")
    print("  effects", {k: v["estimate"] for k, v in eff.items()})
    print("  BF/Sept CPM", pri["bf_week_cpm_vs_september"])


if __name__ == "__main__":
    main()
