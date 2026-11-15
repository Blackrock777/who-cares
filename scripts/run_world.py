"""Generate simulated companies and score the engine and the audience model against known truth.

  python scripts/run_world.py --companies 40          writes out/world/report.json and companies.csv

For each company: train on everything before the last 14 days, forecast those 14 days (they
include Black Friday), and compare with what the simulator produced. Then infer each audience
from the training rows alone and compare with the audience the simulator really used.
"""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from adsim import Engine, load                                   # noqa: E402
from adsim.evaluate import backtest                              # noqa: E402
from adsim.population import AudienceModel, audience_effects     # noqa: E402
from adsim.world import make_company                             # noqa: E402

OUT = ROOT / "out" / "world"


def naive(train, test):
    last = train[train["date"] > train["date"].max() - pd.Timedelta(days=7)]
    g = last.groupby("ad_id")[["clicks", "impressions", "spend"]].sum()
    a = last.groupby("audience_id")[["clicks", "impressions", "spend"]].sum()
    ctr = test["ad_id"].map(g.clicks / g.impressions * 100).fillna(test["audience_id"].map(a.clicks / a.impressions * 100))
    cpm = test["ad_id"].map(g.spend / g.impressions * 1000).fillna(test["audience_id"].map(a.spend / a.impressions * 1000))
    return ctr.values, cpm.values


def score(seed, horizon=14):
    cfg_path, truth = make_company(seed, OUT / "companies" / f"c{seed:03d}")
    b = load(cfg_path)
    h = b["history"]
    cut = h["date"].max() - pd.Timedelta(days=horizon - 1)
    r = {"seed": seed, "vertical": truth["vertical"], "scale": truth["scale"], "audiences": truth["audiences"], "rows": truth["rows"],
         "zero_click_share": round(truth["zero_click_share"], 3), "budget_changes": truth["budget_changes"]}
    bt = backtest(b, cutoffs=[cut], horizon=horizon, draws=400).iloc[0].to_dict()
    for k in ("ctr_log_err_pos", "ctr_wape_clicks", "ctr_pooled_bias", "cpm_log_err", "cpm_bias", "ctr_winners",
              "cov80_cpm_band_known", "cov80_cpm_band_new", "cov80_ctr_simulated_known", "cov80_ctr_simulated_new", "ctr_model"):
        r[k] = bt.get(k)
    train, test = h[h["date"] < cut], h[(h["date"] >= cut) & (h["quality"] == "") & (h["clicks"] > 0)]
    nc, np_ = naive(train, test)
    ok = np.isfinite(nc) & (nc > 0)
    r["naive_ctr_log_err_pos"] = float(np.mean(np.abs(np.log(test["ctr"].values[ok] / nc[ok]))))
    ok = np.isfinite(np_)
    r["naive_cpm_log_err"] = float(np.mean(np.abs(np.log(test["cpm"].values[ok] / np_[ok]))))
    e = Engine(b["cfg"]).fit(train, b["creatives"])
    r.update(k_cpm_true=truth["k_cpm"], k_cpm_fit=e.k["cpm"], budget_variation=e.budget_variation)
    eff = audience_effects(train)
    post = AudienceModel(draws=20000).infer_all(eff, lambda _: truth["vertical"])
    aud = []
    for a, t in truth["audiences_truth"].items():
        if a not in post:
            continue
        q = post[a]
        aud.append({"seed": seed, "audience": a, "vertical": truth["vertical"], "scale": truth["scale"], "warm_true": t["warm"],
                    "p_warm": q["p_warm"], "female_true": t["share_female"], "female_est": q["share_female"]["mean"],
                    "female_prior": q["share_female"]["prior"], "female_p10": q["share_female"]["p10"], "female_p90": q["share_female"]["p90"],
                    "age_true": t["mean_age"], "age_est": q["mean_age"]["mean"], "age_prior": q["mean_age"]["prior"],
                    "age_p10": q["mean_age"]["p10"], "age_p90": q["mean_age"]["p90"]})
    return r, aud


def summarise(c, a):
    rmse = lambda x, y: float(np.sqrt(np.mean((x - y) ** 2)))
    s = {"companies": len(c), "audiences": len(a),
         "by_scale": c.groupby("scale").size().to_dict(), "by_vertical": c.groupby("vertical").size().to_dict(),
         "forecast": {
             "ctr_log_err_engine": c["ctr_log_err_pos"].median(), "ctr_log_err_naive": c["naive_ctr_log_err_pos"].median(),
             "cpm_log_err_engine": c["cpm_log_err"].median(), "cpm_log_err_naive": c["naive_cpm_log_err"].median(),
             "engine_beats_naive_ctr": f"{int((c.ctr_log_err_pos < c.naive_ctr_log_err_pos).sum())}/{len(c)}",
             "engine_beats_naive_cpm": f"{int((c.cpm_log_err < c.naive_cpm_log_err).sum())}/{len(c)}",
             "cov80_cpm_known": c["cov80_cpm_band_known"].mean(), "cov80_cpm_new": c["cov80_cpm_band_new"].mean(),
             "cov80_ctr_known": c["cov80_ctr_simulated_known"].mean(), "cov80_ctr_new": c["cov80_ctr_simulated_new"].mean(),
             "ctr_by_scale": c.groupby("scale")[["ctr_log_err_pos", "naive_ctr_log_err_pos"]].median().round(3).to_dict("index")},
         "budget_elasticity": {
             "with_budget_changes_abs_err": float((c.loc[c.budget_changes > 0, "k_cpm_fit"] - c.loc[c.budget_changes > 0, "k_cpm_true"]).abs().median()),
             "without_budget_changes_abs_err": float((c.loc[c.budget_changes == 0, "k_cpm_fit"] - c.loc[c.budget_changes == 0, "k_cpm_true"]).abs().median()),
             "prior_only_abs_err": float((0.3 - c["k_cpm_true"]).abs().median())},
         "audience": {
             "warm_detection_accuracy": float(((a.p_warm >= 0.5) == a.warm_true).mean()),
             "warm_recall": float((a.loc[a.warm_true, "p_warm"] >= 0.5).mean()) if a.warm_true.any() else None,
             "warm_false_alarm": float((a.loc[~a.warm_true, "p_warm"] >= 0.5).mean()),
             "female_rmse_model": rmse(a.female_est, a.female_true), "female_rmse_prior_only": rmse(a.female_prior, a.female_true),
             "age_rmse_model": rmse(a.age_est, a.age_true), "age_rmse_prior_only": rmse(a.age_prior, a.age_true),
             "female_cov80": float(((a.female_true >= a.female_p10) & (a.female_true <= a.female_p90)).mean()),
             "age_cov80": float(((a.age_true >= a.age_p10) & (a.age_true <= a.age_p90)).mean())}}
    return json.loads(json.dumps(s, default=float))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", type=int, default=40)
    ap.add_argument("--start", type=int, default=1)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    comps, auds = [], []
    for seed in range(a.start, a.start + a.companies):
        t = time.time()
        try:
            r, au = score(seed)
        except Exception as exc:                       # a crash on a simulated company is a finding, not noise
            r, au = {"seed": seed, "error": repr(exc)[:300]}, []
        comps.append(r)
        auds += au
        print(f"company {seed}: {r.get('vertical')} {r.get('scale')} {time.time() - t:.0f}s "
              f"ctr {r.get('ctr_log_err_pos', float('nan')):.3f} vs naive {r.get('naive_ctr_log_err_pos', float('nan')):.3f} {r.get('error', '')}", flush=True)
    c, au = pd.DataFrame(comps), pd.DataFrame(auds)
    c.to_csv(OUT / "companies.csv", index=False)
    au.to_csv(OUT / "audiences.csv", index=False)
    ok = c[c.get("error").isna()] if "error" in c else c
    rep = summarise(ok, au)
    rep["errors"] = c["error"].dropna().tolist() if "error" in c else []
    (OUT / "report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
