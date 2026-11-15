"""Command line:  python -m adsim <config.json> <command> [options]

  forecast                  CTR/CPM per ad-day for the config's future table, with bands and flags
  audiences                 behavioural archetypes, clustered from the data
  whatif --audience ID      budget response curve for one audience over the future window
  simulate                  Monte Carlo outcomes and probability of being the best ad per audience
  creative --json FILE      score a creative that does not exist yet against every audience
  validate                  rolling-origin errors and interval coverage on later data (zero-click days scored)
"""
import argparse
import json
import warnings
from pathlib import Path

import pandas as pd

from . import Engine, load
from .simulate import audiences, simulate, what_if_budget

warnings.filterwarnings("ignore")


def build(config):
    b = load(config)
    e = Engine(b["cfg"]).calibrate(b["history"], b["creatives"]).fit(b["history"], b["creatives"])
    return b, e


def score_creative(b, e, creative, advertiser_id=None):
    """Forecast a new creative in every audience of an advertiser over the future window."""
    c = pd.DataFrame([creative])
    c["creative_id"] = c.get("creative_id", "NEW").astype(str)
    e.add_creatives(c)
    fut = b["future"]
    if advertiser_id:
        fut = fut[fut["advertiser_id"] == advertiser_id]
    rows = fut.drop_duplicates(["date", "audience_id"]).copy()
    rows["creative_id"] = c["creative_id"].iloc[0]
    rows["ad_id"] = "NEW|" + rows["audience_id"]
    rows["age_days"] = (rows["date"] - rows["date"].min()).dt.days
    p = e.predict(rows)
    g = p.groupby("audience_id").agg(ctr=("ctr", "mean"), ctr_lo=("ctr_lo", "mean"), ctr_hi=("ctr_hi", "mean"),
                                     cpm=("cpm", "mean"), cpm_lo=("cpm_lo", "mean"), cpm_hi=("cpm_hi", "mean")).reset_index()
    g["cpc"] = g["cpm"] / (10 * g["ctr"])
    g["archetype"] = g["audience_id"].map(e.arch)
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config"); ap.add_argument("command", choices=["forecast", "audiences", "whatif", "simulate", "creative", "validate"])
    ap.add_argument("--audience"); ap.add_argument("--advertiser"); ap.add_argument("--json"); ap.add_argument("--out", default="out/adsim")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.command == "validate":
        from .evaluate import backtest
        res = backtest(load(a.config))
        res.to_json(out / "validate.json", orient="records", indent=2)
        with pd.option_context("display.width", 200, "display.max_colwidth", 80):
            print(res.T.to_string())
        return
    b, e = build(a.config)
    meta = {"customer": b["cfg"]["name"], "encoder": e.space.used, "trained_through": str(e.trained_through.date()),
            "budget_elasticity": e.k, "budget_elasticity_prior": e.k0, "share_of_rows_with_budget_change": e.budget_variation,
            "budget_change_rows_in_training": e.budget_change_rows,
            "ctr_model": e.ctr_mode, "zero_click_rows": e.zero_click_rows,
            "intervals": {"status": e.interval_status, "refers_to": e.interval_kind, "observed_value_log_width": e.sigma,
                          "rate_error_sd": e.tau, "calibration": getattr(e, "calibration", None)},
            "creative_protocol": e.creative_protocol + (" (text projection fitted on %d training creatives)" % e.space.n_fit_creatives if getattr(e.space, "n_fit_creatives", None) else ""),
            "tree_inputs_left_to_linear_model": e.tree_dropped,
            "missing_optional_inputs": b["missing_optional_inputs"], "rows_excluded_from_training": e.excluded,
            "limitations": ["budget and season flags mark extrapolation beyond the training range",
                            "interval coverage is only known from `adsim validate`", "no conversion, revenue or ROAS is modelled"]}
    if a.command == "forecast":
        res = e.predict(b["future"])
    elif a.command == "audiences":
        res = audiences(e)
    elif a.command == "whatif":
        res = what_if_budget(e, b["future"][b["future"]["audience_id"] == a.audience])
    elif a.command == "simulate":
        res = simulate(e, b["future"])
    else:
        res = score_creative(b, e, json.loads(Path(a.json).read_text()), a.advertiser)
    name = a.command + ("_" + a.audience if a.audience else "")
    res.to_csv(out / f"{name}.csv", index=False)
    (out / "run.json").write_text(json.dumps(meta, indent=2, default=float))
    with pd.option_context("display.width", 220, "display.max_rows", 30):
        print(res.round(3).to_string(index=False) if len(res) <= 30 else res.round(3).head(12).to_string(index=False))
    print(json.dumps(meta, indent=1, default=float))


if __name__ == "__main__":
    main()
