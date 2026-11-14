"""Forecast CTR and CPM per ad per day.

Two learners, blended:
  * a gradient-boosted tree model (captures interactions: ad set x creative x fatigue)
  * a log-linear ridge model (extrapolates cleanly to budgets and seasonal index values
    never seen in the history, which is exactly the Black Week situation)

Both learn the target *detrended* by the 2025 weekly market index, so the model only has
to explain what is specific to this ad, and the Black Week lift comes from the index.

Usage:
  python src/model.py validate   -> trains on data to 1 Nov, scores 2-15 Nov
  python src/model.py predict    -> trains on everything, writes out/predictions.csv
"""
import pickle
import sys
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from features import CAT_COLS, NUM_COLS, RAW, _cpm_prior, history_rows, load_history, load_test

OUT = Path(__file__).resolve().parents[1] / "out"
VAL_START = pd.Timestamp("2026-11-02")

# Columns the tree model sees. The ridge model additionally one-hots the categoricals.
TREE_CATS = ["vertical", "adset_id", "asset_id", "leva", "formato", "adset_rank", "cta"]


def _target(df, metric, detrend=True):
    y = np.log(df[metric].values)
    if detrend:
        idx = df["idx_ctr" if metric == "ctr" else "idx_cpm"].values / 100.0
        y = y - np.log(idx)
    return y


def _untrend(df, yhat, metric, detrend=True):
    if detrend:
        idx = df["idx_ctr" if metric == "ctr" else "idx_cpm"].values / 100.0
        yhat = yhat + np.log(idx)
    return np.exp(yhat)


def _tree(quantile=None):
    kw = dict(max_iter=400, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=15,
              l2_regularization=1.0, categorical_features="from_dtype", random_state=0)
    if quantile is not None:
        kw.update(loss="quantile", quantile=quantile)
    return HistGradientBoostingRegressor(**kw)


def _ridge():
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
        ("num", StandardScaler(), NUM_COLS),
    ])
    return make_pipeline(pre, Ridge(alpha=3.0))


def _frame_for_tree(df):
    X = df[TREE_CATS + NUM_COLS].copy()
    for c in TREE_CATS:
        X[c] = X[c].astype("category")
    return X


class Forecaster:
    def __init__(self, detrend=True, w_tree=0.5):
        self.detrend = detrend
        self.w_tree = w_tree
        self.models = {}

    def fit(self, df):
        if df.empty or (df[["ctr", "cpm"]] <= 0).any().any():
            raise ValueError("Training needs positive CTR/CPM; inspect the quality report.")
        self.trained_through = df["data"].max()
        df = self._context(df)
        for metric in ("ctr", "cpm"):
            y = _target(df, metric, self.detrend)
            tree = _tree().fit(_frame_for_tree(df), y)
            ridge = _ridge().fit(df[CAT_COLS + NUM_COLS], y)
            self.models[metric] = (tree, ridge)
        self.seen_ads = set(df["ad_id"])
        self.seen_assets = set(df["asset_id"])
        return self

    def _context(self, df):
        df = df.copy()
        df["cpm_prior"] = df["data"].dt.strftime("%Y-%m").map(_cpm_prior(self.trained_through))
        return df

    def calibrate(self, df):
        """Conformal bands: 80% quantile of |log residual| on a held-out window,
        separately for ads the model had history for and cold-start ads."""
        if df.empty or df["data"].min() <= self.trained_through:
            raise ValueError("Calibration must be nonempty and strictly after training.")
        p = self.predict(df, calibrated=False)
        self.q = {}
        cold = ~df["ad_id"].isin(self.seen_ads).values
        fallback = earlier_cold_errors(self.trained_through) if not cold.any() else None
        for metric in ("ctr", "cpm"):
            r = np.abs(np.log(df[metric].values) - np.log(p[f"{metric}_pred"].values))
            pooled = finite_quantile(r)
            self.q[metric] = {"warm": finite_quantile(r[~cold]) if (~cold).any() else pooled,
                              "cold": finite_quantile(r[cold]) if cold.any() else finite_quantile(fallback[metric])}
        self.calibration = {"start": str(df["data"].min().date()), "end": str(df["data"].max().date()),
                            "warm_rows": int((~cold).sum()), "cold_rows": int(cold.sum()),
                            "cold_source": "calibration window" if cold.any() else "earlier temporal holdout, ending at training cutoff",
                            "cold_reference_rows": int(cold.sum()) if cold.any() else len(fallback["ctr"]),
                            "interpretation": "Empirical daily intervals; temporal/seasonal shifts can reduce coverage."}
        return self

    def predict(self, df, calibrated=True):
        df = self._context(df)
        out = pd.DataFrame(index=df.index)
        cold = ~df["ad_id"].isin(self.seen_ads).values
        for metric, (tree, ridge) in self.models.items():
            Xt = _frame_for_tree(df)
            p_tree = tree.predict(Xt)
            p_ridge = ridge.predict(df[CAT_COLS + NUM_COLS])
            blend = self.w_tree * p_tree + (1 - self.w_tree) * p_ridge
            out[f"{metric}_pred"] = _untrend(df, blend, metric, self.detrend)
            out[f"{metric}_tree"] = _untrend(df, p_tree, metric, self.detrend)
            out[f"{metric}_ridge"] = _untrend(df, p_ridge, metric, self.detrend)
            if calibrated and getattr(self, "q", None):
                q = np.where(cold, self.q[metric]["cold"], self.q[metric]["warm"])
                out[f"{metric}_lo"] = _untrend(df, blend - q, metric, self.detrend)
                out[f"{metric}_hi"] = _untrend(df, blend + q, metric, self.detrend)
            if metric == "ctr":
                for col in [c for c in out if c.startswith("ctr_")]:
                    out[col] = out[col].clip(upper=100)
        out["cold_start"] = cold.astype(int)
        out["new_asset"] = (~df["asset_id"].isin(self.seen_assets)).astype(int).values
        return out


def finite_quantile(residuals, coverage=0.8):
    """Finite-sample order statistic, rather than interpolating error quantiles.

    The usual exchangeability assumption does not hold automatically for ad time series.
    We therefore verify temporal coverage and do not claim a distribution-free guarantee.
    """
    r = np.sort(np.asarray(residuals, dtype=float))
    if not len(r) or not np.isfinite(r).all():
        raise ValueError("Calibration residuals must be finite and nonempty.")
    return float(r[min(len(r), int(np.ceil((len(r) + 1) * coverage))) - 1])


def earlier_cold_errors(cutoff):
    """Use earlier out-of-time new-ad errors when a calibration week has no new ads.

    The original code substituted the unexplained constant 0.4 for this case.
    Here the last 14 training days are forecast by a model trained before them.
    """
    h = load_history()
    h = h[h["data"] <= cutoff]
    start = cutoff.normalize() - pd.Timedelta(days=13)
    train, held = h[h["data"] < start], h[h["data"] >= start]
    f = Forecaster().fit(train)
    cold = ~held["ad_id"].isin(f.seen_ads)
    reference = held[cold] if cold.any() else held
    p = f.predict(reference)
    return {m: np.abs(np.log(reference[m].values / p[f"{m}_pred"].values)) for m in ["ctr", "cpm"]}


def input_fingerprint():
    digest = hashlib.sha256()
    paths = sorted(RAW.rglob("*.csv")) + [Path(__file__), Path(__file__).with_name("features.py")]
    for path in paths:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def fit_production():
    h = load_history()
    train, val = h[h["data"] < VAL_START], h[h["data"] >= VAL_START]
    calibrated = Forecaster().fit(train).calibrate(val)
    fitted = Forecaster().fit(h)
    fitted.q, fitted.calibration = calibrated.q, calibrated.calibration
    fitted.fingerprint = input_fingerprint()
    return fitted


def naive_baseline(train, test):
    """Last-7-day mean per ad; ads with no history fall back to their ad set's mean."""
    last = train[train["data"] > train["data"].max() - pd.Timedelta(days=7)]
    by_ad = last.groupby("ad_id", observed=True)[["ctr", "cpm"]].mean()
    by_adset = last.groupby("adset_id", observed=True)[["ctr", "cpm"]].mean()
    out = pd.DataFrame(index=test.index)
    for m in ("ctr", "cpm"):
        v = test["ad_id"].map(by_ad[m])
        v = v.fillna(test["adset_id"].astype(str).map(by_adset[m]))
        out[f"{m}_pred"] = v.values
    return out


def score(test, pred, label):
    rows = []
    for m in ("ctr", "cpm"):
        y, p = test[m].values, pred[f"{m}_pred"].values
        mae = np.mean(np.abs(y - p))
        positive = y > 0
        mape = np.mean(np.abs(y[positive] - p[positive]) / y[positive]) * 100 if positive.any() else np.nan
        # ranking quality: per-ad mean over the window
        g = pd.DataFrame({"ad": test["ad_id"].values, "adset": test["adset_id"].astype(str).values, "y": y, "p": p})
        per_ad = g.groupby(["adset", "ad"]).mean(numeric_only=True).reset_index()
        rho = spearmanr(per_ad["y"], per_ad["p"]).correlation
        # winner per ad set (highest CTR / lowest CPM)
        best = "idxmax" if m == "ctr" else "idxmin"
        hits = 0
        for _, grp in per_ad.groupby("adset"):
            hits += int(getattr(grp["y"], best)() == getattr(grp["p"], best)())
        n_sets = per_ad["adset"].nunique()
        cov = ""
        if f"{m}_lo" in pred:
            cov = f"{np.mean((y >= pred[f'{m}_lo'].values) & (y <= pred[f'{m}_hi'].values)) * 100:.0f}%"
        within = [spearmanr(g["y"], g["p"]).statistic for _, g in per_ad.groupby("adset")
                  if len(g) > 1 and g["y"].nunique() > 1 and g["p"].nunique() > 1]
        rows.append(dict(model=label, metric=m, rows=len(y), MAE=round(mae, 3), MAPE=round(mape, 1),
                         MAPE_rows=int(positive.sum()), WAPE=round(np.abs(y-p).sum()/y.sum()*100, 1),
                         spearman=round(rho, 2), within_set_spearman=round(float(np.mean(within)), 2) if within else None,
                         winners=f"{hits}/{n_sets}", coverage80=cov))
    return rows


def validate():
    h = load_history()
    train, val = h[h["data"] < VAL_START], h[h["data"] >= VAL_START]
    print(f"train {len(train)} rows to {train['data'].max().date()}, val {len(val)} rows "
          f"{val['data'].min().date()}..{val['data'].max().date()}, "
          f"cold-start ads in val: {sorted(set(val['ad_id']) - set(train['ad_id']))}")
    rows = []
    rows += score(val, naive_baseline(train, val), "naive last-7d")
    for detrend in (False, True):
        for w in (1.0, 0.0, 0.5):
            f = Forecaster(detrend=detrend, w_tree=w).fit(train)
            name = {1.0: "tree", 0.0: "ridge", 0.5: "blend"}[w] + (" +index" if detrend else "")
            rows += score(val, f.predict(val), name)
    # honest coverage check: calibrate bands on 2-8 Nov, score coverage on 9-15 Nov
    mid = pd.Timestamp("2026-11-09")
    f = Forecaster(detrend=True, w_tree=0.5).fit(train).calibrate(val[val["data"] < mid])
    later = val[val["data"] >= mid]
    later_predictions = f.predict(later)
    rows += score(later, later_predictions, "blend +index, empirical intervals (9-15 Nov)")
    interval_report = {"calibration": f.calibration, "log_widths": f.q, "coverage": {}}
    for label, mask in [("all", np.ones(len(later), dtype=bool)),
                        ("known_ads", later.ad_id.isin(f.seen_ads).values),
                        ("new_ads", ~later.ad_id.isin(f.seen_ads).values)]:
        interval_report["coverage"][label] = {"rows": int(mask.sum())}
        for metric in ["ctr", "cpm"]:
            y = later.loc[mask, metric].to_numpy()
            lo, hi = later_predictions.loc[mask, f"{metric}_lo"], later_predictions.loc[mask, f"{metric}_hi"]
            interval_report["coverage"][label][metric] = float(np.mean((y >= lo) & (y <= hi))) if len(y) else None
    (OUT / "interval_validation.json").write_text(json.dumps(interval_report, indent=2), encoding="utf-8")
    res = pd.DataFrame(rows)
    print(res.to_string(index=False))
    res.to_csv(OUT / "validation.csv", index=False)

    # cold-start detail: the ads launched inside the validation window
    f = Forecaster(detrend=True, w_tree=0.5).fit(train)
    p = f.predict(val)
    cold = sorted(set(val["ad_id"]) - set(train["ad_id"]))
    d = val.assign(ctr_pred=p["ctr_pred"].values, cpm_pred=p["cpm_pred"].values)
    d = d[d["ad_id"].isin(cold)].groupby("ad_id", observed=True)[["ctr", "ctr_pred", "cpm", "cpm_pred"]].mean().round(3)
    print("\nCold-start ads (no history at train time):")
    print(d.to_string())
    # Report every validation outcome too: MAPE excludes only undefined zero denominators,
    # while MAE/WAPE include zeros. No claim that the organisers confirmed our exclusions.
    raw = load_history(include_flagged=True)
    raw_val = raw[raw["data"] >= VAL_START]
    details = []
    for label, subset in [("all supplied validation rows", raw_val), ("clean validation", val)]:
        details += score(subset, f.predict(subset), label)
    pv = f.predict(val)
    for label, mask in [("known ads", val["ad_id"].isin(f.seen_ads)),
                        ("new ads", ~val["ad_id"].isin(f.seen_ads))]:
        details += score(val[mask], pv.loc[val[mask].index], label)
    for field in ["vertical", "adset_id", "data"]:
        for key, group in val.groupby(field, observed=True):
            details += score(group, pv.loc[group.index], f"{field}: {key}")
    pd.DataFrame(details).to_csv(OUT / "validation_breakdown.csv", index=False)
    detail = val[["data", "ad_id", "adset_id", "asset_id", "vertical", "ctr", "cpm"]].join(pv)
    detail.to_csv(OUT / "validation_predictions.csv", index=False)
    flagged = history_rows().query("quality_reason != ''")
    flagged.to_csv(OUT / "quality_flags.csv", index=False)


def rolling_validate():
    """Compare blend weights on three earlier 14-day windows, ending before 2 Nov.

    Keep the official 2-15 Nov window out of this comparison. Rows are dependent,
    so these folds are evidence of stability, not independent replications.
    """
    h, rows = load_history(), []
    for start in ["2026-09-21", "2026-10-05", "2026-10-19"]:
        end = pd.Timestamp(start) + pd.Timedelta(days=14)
        train = h[h["data"] < start]
        val = h[(h["data"] >= start) & (h["data"] < end)]
        f = Forecaster().fit(train)
        for weight, name in [(0.0, "ridge +index"), (0.5, "blend +index"), (1.0, "tree +index")]:
            f.w_tree = weight
            p = f.predict(val)
            for row in score(val, p, name):
                m = row["metric"]
                row.update(fold=start, train_end=str(train["data"].max().date()),
                           log_MAE=float(np.abs(np.log(val[m].values / p[f"{m}_pred"].values)).mean()))
                rows.append(row)
        for row in score(val, naive_baseline(train, val), "naive last-7d"):
            row.update(fold=start, train_end=str(train["data"].max().date()))
            rows.append(row)
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "rolling_validation.csv", index=False)
    print(result.groupby(["model", "metric"])[["MAE", "MAPE", "log_MAE"]].mean().round(4).to_string())
    return result


def predict():
    h = load_history()
    t = load_test()
    f = fit_production()
    p = f.predict(t)
    print("empirical 80% log-bands:", f.q)
    with open(OUT / "model.pkl", "wb") as handle:
        pickle.dump(f, handle)
    cols = ["data", "vertical", "campaign_id", "adset_id", "ad_id", "asset_id", "leva", "formato", "budget_giornaliero_adset"]
    res = pd.concat([t[cols].reset_index(drop=True), p.reset_index(drop=True)], axis=1)
    res["data"] = res["data"].dt.date
    res = res.round(4)
    from contracts import check_predictions
    checks = check_predictions(pd.read_csv(RAW / "da_prevedere.csv"), res)
    res.to_csv(OUT / "predictions.csv", index=False)
    import sklearn
    metadata = {"input_sha256": f.fingerprint, "training_rows": len(h), "raw_history_rows": len(history_rows()),
                "flagged_rows": int(history_rows().quality_reason.ne("").sum()),
                "trained_through": str(f.trained_through.date()), "calibration": f.calibration,
                "intervals": f.q, "output_checks": checks, "sklearn_version": sklearn.__version__,
                "python_version": sys.version.split()[0], "numpy_version": np.__version__, "pandas_version": pd.__version__,
                "new_ad_ids": sorted(set(t.ad_id) - f.seen_ads), "new_asset_ids": sorted(set(t.asset_id) - f.seen_assets),
                "model": "50/50 log-space tree/ridge; supported by pre-November rolling comparison",
                "seasonality": "2025 benchmark aligned 364 days back; Black Friday transfer is untested"}
    (OUT / "run_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    seasonal = t[["data", "vertical", "idx_ctr", "idx_cpm", "cpm_prior"]].drop_duplicates().copy()
    last_year = seasonal["data"] - pd.Timedelta(days=364)
    seasonal["benchmark_week"] = last_year - pd.to_timedelta(last_year.dt.weekday, unit="D")
    seasonal.to_csv(OUT / "seasonality_assumptions.csv", index=False)
    summary = (res.groupby(["vertical", "adset_id", "ad_id", "asset_id", "leva", "formato"], observed=True)
               [["ctr_pred", "ctr_lo", "ctr_hi", "cpm_pred", "cpm_lo", "cpm_hi", "cold_start"]].mean().round(3).reset_index())
    summary.to_csv(OUT / "summary_by_ad.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    # when run as a script, make the pickled Forecaster resolve as model.Forecaster
    sys.modules["model"] = sys.modules[__name__]
    Forecaster.__module__ = "model"
    OUT.mkdir(exist_ok=True)
    {"validate": validate, "predict": predict, "rolling": rolling_validate}[sys.argv[1]]()
