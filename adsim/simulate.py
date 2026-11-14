"""What-if and Monte Carlo on top of a fitted Engine. Structural, so every curve can be inspected."""
import numpy as np
import pandas as pd


def what_if_budget(engine, rows, multipliers=(0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)):
    """Response of one audience-day (or any set of rows) to scaling its budget.

    Spend is assumed to follow budget and to be split equally across the rows of an audience-day.
    Returns per multiplier: CPM, CTR, impressions, clicks, CPC and clicks gained per extra euro.
    """
    out = []
    n = rows.groupby(["date", "audience_id"])["ad_id"].transform("size")
    for m in multipliers:
        p = engine.predict(rows, budget_multiplier=m)
        spend = rows["budget"].values * m / n.values
        impr = spend / p["cpm"].values * 1000
        clicks = impr * p["ctr"].values / 100
        out.append(dict(multiplier=m, budget=float((rows["budget"].values * m / n.values).sum()), cpm=float(np.average(p["cpm"], weights=impr)),
                        ctr=float(clicks.sum() / impr.sum() * 100), impressions=float(impr.sum()), clicks=float(clicks.sum()),
                        cpc=float(spend.sum() / clicks.sum()), extrapolated=bool(p["budget_extrapolated"].any())))
    t = pd.DataFrame(out)
    t["marginal_clicks_per_euro"] = t["clicks"].diff() / t["budget"].diff()
    return t


def simulate(engine, rows, draws=2000, seed=0):
    """Draw outcomes: parameter uncertainty (calibrated log-normal) x click-count noise (Poisson).

    Returns per row the 10/50/90% quantiles of impressions, clicks and observed CTR, plus the
    probability that each ad has the highest CTR within its audience-day.
    """
    rng = np.random.default_rng(seed)
    p = engine.predict(rows)
    n = rows.groupby(["date", "audience_id"])["ad_id"].transform("size").values
    spend = rows["budget"].values / n
    z = 1.2816                                                    # 80% band -> sigma
    s_ctr = np.log(p["ctr_hi"].values / p["ctr"].values) / z
    s_cpm = np.log(p["cpm_hi"].values / p["cpm"].values) / z
    ctr = p["ctr"].values * np.exp(rng.normal(0, 1, (draws, len(p))) * s_ctr)
    cpm = p["cpm"].values * np.exp(rng.normal(0, 1, (draws, len(p))) * s_cpm)
    impr = spend / cpm * 1000
    clicks = rng.poisson(impr * ctr / 100)
    obs = clicks / impr * 100
    res = p[["date", "ad_id", "audience_id", "creative_id"]].copy()
    for name, arr in [("impressions", impr), ("clicks", clicks), ("ctr_observed", obs)]:
        res[name + "_p10"], res[name + "_p50"], res[name + "_p90"] = np.quantile(arr, [0.1, 0.5, 0.9], axis=0)
    freq = rows["audience_id"].map(engine.freq).values
    res["reach_p50"] = res["impressions_p50"] / np.where(np.isfinite(freq), freq, 1.0)
    grp = pd.factorize(rows["date"].astype(str) + "|" + rows["audience_id"])[0]
    win = np.zeros(len(p))
    for g in np.unique(grp):
        idx = np.where(grp == g)[0]
        best = idx[obs[:, idx].argmax(axis=1)]
        win[idx] = np.bincount(best, minlength=len(p))[idx] / draws
    res["p_best_in_audience"] = win
    return res


def audiences(engine):
    """Behavioural description of each audience from its fingerprint; no demographics are inferred."""
    f = engine.fingerprint.copy()

    def describe(r):
        bits = []
        bits.append("responds %s its advertiser's average" % ("well above" if r.z_ctr > 0.8 else "above" if r.z_ctr > 0.2 else "below" if r.z_ctr < -0.2 else "near"))
        bits.append("costs %s to reach" % ("much more" if r.z_cpm > 0.8 else "more" if r.z_cpm > 0.2 else "less" if r.z_cpm < -0.2 else "about average"))
        if "z_freq" in r and np.isfinite(r.z_freq):
            bits.append("sees ads repeatedly (small pool)" if r.z_freq > 0.8 else "rarely sees an ad twice (large pool)")
        return "; ".join(bits)
    f["behaviour"] = f.apply(describe, axis=1)
    f["ctr_level_pct"], f["cpm_level_eur"] = np.exp(f["ctr"]), np.exp(f["cpm"])
    return f[["advertiser_id", "audience_id", "archetype", "ctr_level_pct", "cpm_level_eur", "behaviour"]]
