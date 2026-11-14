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
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from features import CAT_COLS, NUM_COLS, load_history, load_test

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
        for metric in ("ctr", "cpm"):
            y = _target(df, metric, self.detrend)
            tree = _tree().fit(_frame_for_tree(df), y)
            ridge = _ridge().fit(df[CAT_COLS + NUM_COLS], y)
            self.models[metric] = (tree, ridge)
        self.seen_ads = set(df["ad_id"])
        return self

    def calibrate(self, df):
        """Conformal bands: 80% quantile of |log residual| on a held-out window,
        separately for ads the model had history for and cold-start ads."""
        p = self.predict(df, calibrated=False)
        self.q = {}
        cold = ~df["ad_id"].isin(self.seen_ads).values
        for metric in ("ctr", "cpm"):
            r = np.abs(np.log(df[metric].values) - np.log(p[f"{metric}_pred"].values))
            self.q[metric] = {"warm": float(np.quantile(r[~cold], 0.8)) if (~cold).any() else 0.3,
                              "cold": float(np.quantile(r[cold], 0.8)) if cold.any() else 0.4}
        return self

    def predict(self, df, calibrated=True):
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
        out["cold_start"] = cold.astype(int)
        return out


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
        mape = np.mean(np.abs(y - p) / y) * 100
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
        rows.append(dict(model=label, metric=m, MAE=round(mae, 3), MAPE=round(mape, 1),
                         spearman=round(rho, 2), winners=f"{hits}/{n_sets}", coverage80=cov))
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
    rows += score(val[val["data"] >= mid], f.predict(val[val["data"] >= mid]), "blend +index, conformal (9-15 Nov)")
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


def predict():
    h = load_history()
    t = load_test()
    train, val = h[h["data"] < VAL_START], h[h["data"] >= VAL_START]
    q = Forecaster(detrend=True, w_tree=0.5).fit(train).calibrate(val).q
    f = Forecaster(detrend=True, w_tree=0.5).fit(h)
    f.q = q
    p = f.predict(t)
    print("conformal 80% log-bands:", q)
    pickle.dump(f, open(OUT / "model.pkl", "wb"))
    cols = ["data", "vertical", "campaign_id", "adset_id", "ad_id", "asset_id", "leva", "formato", "budget_giornaliero_adset"]
    res = pd.concat([t[cols].reset_index(drop=True), p.reset_index(drop=True)], axis=1)
    res["data"] = res["data"].dt.date
    res = res.round(4)
    res.to_csv(OUT / "predictions.csv", index=False)
    summary = (res.groupby(["vertical", "adset_id", "ad_id", "asset_id", "leva", "formato"], observed=True)
               [["ctr_pred", "ctr_lo", "ctr_hi", "cpm_pred", "cpm_lo", "cpm_hi", "cold_start"]].mean().round(3).reset_index())
    summary.to_csv(OUT / "summary_by_ad.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    # when run as a script, make the pickled Forecaster resolve as model.Forecaster
    sys.modules["model"] = sys.modules[__name__]
    Forecaster.__module__ = "model"
    OUT.mkdir(exist_ok=True)
    {"validate": validate, "predict": predict}[sys.argv[1]]()
