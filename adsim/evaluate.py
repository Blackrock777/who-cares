"""Rolling-origin evaluation that stays meaningful when clicks are zero.

For each cut-off the engine is calibrated and fitted on rows strictly before it, then scored on
the next `horizon` days. Valid zero-click days are scored. Rows excluded as invalid or suspicious
are counted and reported, and the headline metrics are also given with them included, so dropping
hard rows cannot pass as an accuracy gain.

CTR metrics: MAE in percentage points, WAPE on clicks at the realised impressions, pooled-rate
bias and mean Poisson deviance are all defined at zero. Log error and MAPE are reported on
positive rows only, with the count.
"""
import numpy as np
import pandas as pd

from .data import flag_anomalies
from .engine import Engine
from .simulate import simulate


def _ctr_block(rows, p, prefix=""):
    c, n, r = rows["clicks"].values.astype(float), rows["impressions"].values.astype(float), p["ctr"].values
    m = n * r / 100
    pos = c > 0
    dev = 2 * (np.where(pos, c * np.log(np.where(pos, c, 1) / m), 0.0) - (c - m))
    out = {"ctr_mae_pp": float(np.mean(np.abs(c / n * 100 - r))), "ctr_wape_clicks": float(np.abs(c - m).sum() / max(c.sum(), 1)),
           "ctr_pooled_bias": float(m.sum() / max(c.sum(), 1) - 1), "ctr_poisson_deviance": float(dev.mean()),
           "ctr_log_err_pos": float(np.mean(np.abs(np.log(c[pos] / n[pos] * 100 / r[pos])))) if pos.any() else float("nan"),
           "ctr_mape_pos": float(np.mean(np.abs(c[pos] / n[pos] * 100 - r[pos]) / (c[pos] / n[pos] * 100)) * 100) if pos.any() else float("nan"),
           "rows": int(len(c)), "zero_click_rows_scored": int((~pos).sum())}
    return {prefix + k: v for k, v in out.items()}


def backtest(bundle, cutoffs=None, horizon=14, draws=800):
    h, creatives, cfg = bundle["history"], bundle["creatives"], bundle["cfg"]
    days = np.sort(h["date"].unique())
    if cutoffs is None:
        cutoffs = [days[-horizon * k] for k in (3, 2, 1) if len(days) >= horizon * k + 21]
        if not cutoffs:
            raise ValueError("Not enough history to back-test: need at least %d days, have %d." % (horizon + 21, len(days)))
    out = []
    for cut in pd.to_datetime(cutoffs):
        train = h[h["date"] < cut]
        window = h[(h["date"] >= cut) & (h["date"] < cut + pd.Timedelta(days=horizon))]
        e = Engine(cfg).calibrate(train, creatives).fit(train, creatives)
        flags = flag_anomalies(pd.concat([train, window]).drop(columns=["quality"], errors="ignore"))
        flags = flags[flags["date"] >= cut]
        valid, usable = flags[flags["quality"] == ""], flags[flags["quality"] != "invalid"]
        p = e.predict(valid)
        r = {"cutoff": str(cut.date()), "ctr_model": e.ctr_mode, "creative_protocol": e.creative_protocol,
             "train_exclusions": e.excluded, "eval_exclusions": flags.loc[flags["quality"] != "", "quality"].value_counts().to_dict()}
        r.update(_ctr_block(valid, p))
        r.update({k: v for k, v in _ctr_block(usable, e.predict(usable), "all_rows_").items() if k in ("all_rows_ctr_mae_pp", "all_rows_ctr_wape_clicks", "all_rows_rows")})
        y, q = valid["cpm"].values, p["cpm"].values
        r.update(cpm_log_err=float(np.mean(np.abs(np.log(y / q)))), cpm_mape=float(np.mean(np.abs(y - q) / y) * 100), cpm_bias=float(np.mean(np.log(q / y))))
        new = p["new_ad"].values
        if new.any():
            r.update({"new_ad_" + k: v for k, v in _ctr_block(valid[new], p[new]).items() if k in ("ctr_mae_pp", "ctr_wape_clicks", "rows")})
            r["new_ad_cpm_log_err"] = float(np.mean(np.abs(np.log(y[new] / q[new]))))
        g = pd.DataFrame({"s": valid["audience_id"].values, "a": valid["ad_id"].values, "c": valid["clicks"].values, "n": valid["impressions"].values,
                          "m": valid["impressions"].values * p["ctr"].values / 100}).groupby(["s", "a"]).sum().reset_index()
        g["y"], g["q"] = g["c"] / g["n"], g["m"] / g["n"]
        sets = [x for _, x in g.groupby("s") if len(x) > 1]
        r["ctr_winners"] = "%d/%d" % (sum(x.y.idxmax() == x.q.idxmax() for x in sets), len(sets))
        # interval coverage: bands were fixed before the cut-off, outcomes are after it
        r["interval_status"] = e.interval_status
        if e.tau is not None:
            def cov(lo, hi, obs, mask):
                return float(np.mean((obs[mask] >= lo[mask]) & (obs[mask] <= hi[mask]))) if mask.any() else float("nan")
            s = simulate(e, valid.assign(budget=valid["spend"].values * valid.groupby(["date", "audience_id"])["ad_id"].transform("size").values), draws=draws)
            obs = (valid["clicks"] / valid["impressions"] * 100).values
            for name, mask in [("known", ~new), ("new", new)]:
                r[f"cov80_cpm_band_{name}"] = cov(p["cpm_lo"].values, p["cpm_hi"].values, y, mask)
                r[f"cov80_ctr_simulated_{name}"] = cov(s["ctr_observed_p10"].values, s["ctr_observed_p90"].values, obs, mask)
                if e.ctr_mode == "lognormal":
                    r[f"cov80_ctr_band_{name}"] = cov(p["ctr_lo"].values, p["ctr_hi"].values, obs, mask)
        out.append(r)
    return pd.DataFrame(out)
