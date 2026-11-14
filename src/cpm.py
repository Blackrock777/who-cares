"""CPM forecaster: three budget-neutral learners on a de-noised seasonal index.

Why CPM has its own model (evidence in AUDIT.md, section "ML audit, 14 Nov"):
  * CPM is an auction price. It moves with the market season and with how hard the ad set's
    budget is pushed, far more than with the creative.
  * The planned Black Week budgets are up to 2.5x the starting budget; history holds one
    budget change (NDL ad set 4, 45 -> 90 euro for a week). Boosted trees cannot extrapolate
    beyond that, so the budget effect is estimated once as a constant elasticity and applied
    to every learner.
  * The 2025 weekly index is the seasonal curve plus week-to-week noise that 2026 does not
    repeat. `features.py` supplies a de-noised index (`idx_cpm_s`); the learners see the
    target divided by it and no other seasonal feature, so nothing can cancel the index.

Prediction = exp(mean of learners) x idx_cpm_s x budget_ratio ** k
Learners: hierarchical ridge, boosted trees, and the ad's own last-7-day level.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

TAGS = ["hook_first2s", "logo_first", "talks_to_camera", "heavy_text", "discount_late", "timer",
        "person", "studio", "price_slash", "reviews", "black_bg"]
NUMS = TAGS + ["video_s", "discount_pct", "headline_len", "text_len"]
TREE_CATS = ["vertical", "adset_id", "asset_id", "leva", "formato", "rank", "cta"]
TREE_NUMS = TAGS + ["video_s", "discount_pct", "weeks", "log_days", "weekday", "headline_len", "text_len"]


def _prep(df):
    d = pd.DataFrame(index=df.index)
    for c in ["vertical", "adset_id", "asset_id", "leva", "formato", "cta", "ad_id"]:
        d[c] = df[c].astype(str).values
    d["rank"] = df["adset_rank"].astype(str).values
    for c in NUMS + ["log_days", "weekday"]:
        d[c] = df[c].astype(float).values
    d["weeks"] = df["days_since_launch"].values / 7.0
    d["wk0"] = (df["days_since_launch"].values < 7).astype(float)
    d["lbr"] = np.log(df["budget_ratio"].values.astype(float))
    d["lidx"] = np.log(df["idx_cpm_s"].values / 100.0)
    d["data"] = df["data"].values
    return d


class _Hier:
    """Ridge with group-specific penalties: ad set levels are almost free, creative and ad
    effects are shrunk toward them, interactions and tags more so (partial pooling)."""

    def __init__(self, with_budget):
        self.with_budget = with_budget

    def _X(self, d, fit=False):
        if fit:
            self.cats = {}
        blocks = []

        def dummies(name, s, scale):
            if fit:
                self.cats[name] = {c: i for i, c in enumerate(sorted(s.unique()))}
            idx = self.cats[name]
            M = np.zeros((len(s), len(idx)))
            for i, v in enumerate(s.values):
                j = idx.get(v)
                if j is not None:
                    M[i, j] = scale
            blocks.append(M)

        dummies("adset", d.adset_id, 3.0)
        dummies("asset", d.asset_id, 1.0)
        dummies("leva", d.leva, 1.0)
        dummies("formato", d.formato, 1.0)
        dummies("wd", d.weekday.astype(int).astype(str), 0.5)
        dummies("ad", d.ad_id, 0.7)
        dummies("rk_leva", d["rank"] + "|" + d.leva, 0.7)
        dummies("rk_fmt", d["rank"] + "|" + d.formato, 0.7)
        dummies("vert_fmt", d.vertical + "|" + d.formato, 0.7)
        num = d[NUMS].values
        if fit:
            self.mu, self.sd = num.mean(0), num.std(0) + 1e-9
        blocks.append((num - self.mu) / self.sd * 0.5)
        fat = [d.weeks.values, d.log_days.values, d.wk0.values]
        fat += [d.weeks.values * (d["rank"] == r).values for r in "1234"]
        blocks.append(np.column_stack(fat))
        if self.with_budget:
            blocks.append(d[["lbr"]].values * 5.0)
        return np.hstack(blocks)

    def fit(self, d, y):
        self.model = Ridge(alpha=1.0).fit(self._X(d, fit=True), y)
        return self

    def predict(self, d):
        return self.model.predict(self._X(d))


class CpmModel:
    def fit(self, df):
        d = _prep(df)
        y = np.log(df["cpm"].values) - d.lidx.values
        # Stage 1: budget elasticity, with ad effects and fatigue controlled for.
        stage1 = _Hier(with_budget=True).fit(d, y)
        self.k = float(stage1.model.coef_[-1] * 5.0)
        self.budget_ratio_seen = (float(df["budget_ratio"].min()), float(df["budget_ratio"].max()))
        # Stage 2: learners on the budget-neutral target.
        yn = y - self.k * d.lbr.values
        self.hier = _Hier(with_budget=False).fit(d, yn)
        self.tree_cats = {c: sorted(d[c].unique()) for c in TREE_CATS}
        self.tree = HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=15,
            l2_regularization=1.0, categorical_features="from_dtype", random_state=0).fit(self._tree_X(d), yn)
        recent = pd.Timestamp(d.data.max()) - pd.Timedelta(days=7)
        last = d.assign(yn=yn)[d.data > recent]
        self.level_ad = last.groupby("ad_id").yn.mean().to_dict()
        self.level_adset = last.groupby("adset_id").yn.mean().to_dict()
        self.seen_ads = set(d.ad_id)
        return self

    def _tree_X(self, d):
        X = d[TREE_CATS + TREE_NUMS].copy()
        for c in TREE_CATS:
            X[c] = pd.Categorical(X[c], categories=self.tree_cats[c])
        return X

    def components(self, df):
        """Each learner's forecast in euro, budget and season applied. For the audit trail."""
        d = _prep(df)
        scale = d.lidx.values + self.k * d.lbr.values
        level = d.ad_id.map(self.level_ad)
        level = level.fillna(d.adset_id.map(self.level_adset))
        parts = {"hier": self.hier.predict(d), "tree": self.tree.predict(self._tree_X(d)), "level": level.values}
        cold = ~d.ad_id.isin(self.seen_ads).values
        usable = np.isfinite(parts["level"]) & ~cold
        blend = np.where(usable, (parts["hier"] + parts["tree"] + np.nan_to_num(parts["level"])) / 3.0,
                         (parts["hier"] + parts["tree"]) / 2.0)
        out = {name: np.exp(v + scale) for name, v in parts.items()}
        out["pred"] = np.exp(blend + scale)
        return out

    def predict(self, df):
        return self.components(df)["pred"]
