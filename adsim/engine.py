"""The forecasting and simulation engine. Company-agnostic: it sees only the canonical frame.

log KPI = audience level + creative effect + ad effect + fatigue + log(season) + k * log(budget / base budget) + noise

* Levels are partially pooled (group-wise ridge penalties): an ad with little data falls back on
  its creative, its audience archetype and its advertiser.
* Season enters only by division and multiplication, so no learner can cancel or amplify it.
* k (budget elasticity) starts at a shipped prior and moves toward the customer's own budget
  changes in proportion to how much budget variation their history contains.
* Audience archetypes are clustered from behaviour on the training rows; no IDs or names are read.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

from .creative import CreativeSpace

KPIS = ("ctr", "cpm")


class _Hier:
    def __init__(self, blocks):
        self.blocks = blocks                      # list of (kind, name, scale)

    def _X(self, d, fit=False):
        if fit:
            self.cats, self.stats = {}, {}
        out = []
        for kind, name, scale in self.blocks:
            if kind == "cat":
                s = d[name].astype(str)
                if fit:
                    self.cats[name] = {c: i for i, c in enumerate(sorted(s.unique()))}
                idx = self.cats[name]
                M = np.zeros((len(s), len(idx)))
                rows = [(i, idx[v]) for i, v in enumerate(s.values) if v in idx]
                if rows:
                    r, c = zip(*rows)
                    M[list(r), list(c)] = scale
                out.append(M)
            elif kind == "std":
                v = d[name].values.astype(float)
                if fit:
                    self.stats[tuple(name)] = (v.mean(0), v.std(0) + 1e-9)
                mu, sd = self.stats[tuple(name)]
                out.append((v - mu) / sd * scale)
            else:
                out.append(d[name].values.astype(float) * scale)
        return np.hstack(out)

    def fit(self, d, y, weight=None):
        self.model = Ridge(alpha=1.0).fit(self._X(d, True), y, sample_weight=weight)
        return self

    def predict(self, d):
        return self.model.predict(self._X(d))


class Engine:
    def __init__(self, cfg, level_days=7):
        self.cfg, self.level_days = cfg, level_days
        self.blend = cfg.get("blend", {"ctr": ["hier"], "cpm": ["hier", "tree", "level"]})
        self.k0 = cfg.get("priors", {}).get("budget_elasticity", {"ctr": 0.0, "cpm": 0.3})
        self.prior_weight = cfg.get("priors", {}).get("prior_weight", 1.0)
        self.creative_cats = (cfg.get("creatives") or {}).get("categorical", [])

    # ---------- features ----------
    def _archetypes(self, h):
        """Cluster audiences on behaviour relative to their own advertiser."""
        g = h.groupby(["advertiser_id", "audience_id"]).agg(
            ctr=("ctr", lambda x: np.log(x).mean()), cpm=("cpm", lambda x: np.log(x).mean()),
            freq=("frequency", lambda x: np.log(x).mean())).reset_index()
        cols = ["ctr", "cpm"] + (["freq"] if g["freq"].notna().all() else [])
        z = g[cols] - g.groupby("advertiser_id")[cols].transform("mean")
        z = z / (z.std() + 1e-9)
        n = int(max(1, min(self.cfg.get("archetypes", 4), len(g) // 2)))
        km = KMeans(n, n_init=20, random_state=0).fit(z.values)
        order = np.argsort(np.argsort(km.cluster_centers_[:, 0]))      # label by response level
        g["archetype"] = ["A%d" % order[c] for c in km.labels_]
        self.fingerprint = g.join(z.add_prefix("z_"))
        return dict(zip(g["audience_id"], g["archetype"]))

    def _design(self, df):
        d = df.copy()
        d["archetype"] = d["audience_id"].map(self.arch).fillna("A?")
        d["weeks"] = d["age_days"] / 7.0
        d["log_age"] = np.log1p(d["age_days"])
        d["wk0"] = (d["age_days"] < 7).astype(float)
        d["weekday"] = d["date"].dt.weekday.astype(str)
        feats = self.cfeat.reindex(d["creative_id"].values)
        if len(self.cfeat.columns) and feats.isna().any().any():
            raise ValueError("Unknown creative: add it to the creatives table before forecasting.")
        for c in self.cfeat.columns:
            d[c] = feats[c].values
        cats = self.ccat.reindex(d["creative_id"].values)
        for c in self.creative_cats:
            d["c_" + c] = cats[c].astype(str).values
            d["ax_" + c] = d["archetype"] + "|" + d["c_" + c]
            d["vx_" + c] = d["advertiser_id"] + "|" + d["c_" + c]
        for a in self.arch_levels:
            d["fat_" + a] = d["weeks"] * (d["archetype"] == a)
        return d

    def _blocks(self, with_budget):
        b = [("cat", "audience_id", 3.0), ("cat", "creative_id", 1.0), ("cat", "ad_id", 0.7), ("cat", "weekday", 0.5)]
        for c in self.creative_cats:
            b += [("cat", "c_" + c, 1.0), ("cat", "ax_" + c, 0.7), ("cat", "vx_" + c, 0.7)]
        if len(self.cfeat.columns):
            b += [("std", list(self.cfeat.columns), 0.5)]
        b += [("raw", ["weeks", "log_age", "wk0"] + ["fat_" + a for a in self.arch_levels], 1.0)]
        if with_budget:
            b += [("raw", ["lbr"], 5.0 / max(self.prior_weight, 1e-6) ** 0.5)]
        return b

    # ---------- fit ----------
    def fit(self, history, creatives):
        h = history[history["quality"] == ""].copy()
        self.trained_through = h["date"].max()
        self.arch = self._archetypes(h)
        self.arch_levels = sorted(set(self.arch.values()))
        self.space = CreativeSpace(self.cfg).fit(creatives)
        self.cfeat = self.space.transform(creatives)
        self.ccat = creatives.set_index("creative_id")[self.creative_cats] if self.creative_cats else pd.DataFrame(index=creatives["creative_id"])
        self.cfeat = self.cfeat.reindex(self.cfeat.index.union(h["creative_id"].unique()))
        d = self._design(h)
        self.k, self.m, self.level, self.tree_cols = {}, {}, {}, None
        tcat = ["advertiser_id", "audience_id", "creative_id", "archetype"] + ["c_" + c for c in self.creative_cats]
        tnum = list(self.cfeat.columns) + ["weeks", "log_age"]
        self.tcat, self.tnum = tcat, tnum
        self.tlevels = {c: sorted(d[c].astype(str).unique()) for c in tcat}
        for kpi in KPIS:
            y = np.log(d[kpi].values) - np.log(d[f"season_{kpi}"].values / 100)
            # stage 1: elasticity = prior + what this customer's own budget changes say
            s1 = _Hier(self._blocks(True)).fit(d, y - self.k0[kpi] * d["lbr"].values)
            scale = self._blocks(True)[-1][2]
            self.k[kpi] = float(self.k0[kpi] + s1.model.coef_[-1] * scale)
            yn = y - self.k[kpi] * d["lbr"].values
            hier = _Hier(self._blocks(False)).fit(d, yn)
            tree = None
            if "tree" in self.blend[kpi]:
                tree = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=15,
                                                     l2_regularization=1.0, categorical_features="from_dtype", random_state=0).fit(self._tx(d), yn)
            last = d.assign(yn=yn)[d["date"] > self.trained_through - pd.Timedelta(days=self.level_days)]
            self.level[kpi] = (last.groupby("ad_id")["yn"].mean().to_dict(), last.groupby("audience_id")["yn"].mean().to_dict())
            self.m[kpi] = (hier, tree)
        self.seen_ads, self.seen_creatives = set(d["ad_id"]), set(d["creative_id"])
        self.seen_lbr = (float(d["lbr"].min()), float(d["lbr"].max()))
        self.seen_season = {k: (float(d[f"season_{k}"].min()), float(d[f"season_{k}"].max())) for k in KPIS}
        self.budget_variation = float((d["lbr"].abs() > 1e-9).mean())
        self.freq = h.groupby("audience_id")["frequency"].median().to_dict()
        self.sigma = getattr(self, "sigma", None)
        return self

    def add_creatives(self, creatives):
        """Register creatives that did not exist at fit time (no refit: encoder and model are frozen)."""
        creatives = creatives.assign(creative_id=creatives["creative_id"].astype(str))
        self.cfeat = pd.concat([self.cfeat[~self.cfeat.index.isin(creatives["creative_id"])], self.space.transform(creatives)])
        if self.creative_cats:
            self.ccat = pd.concat([self.ccat[~self.ccat.index.isin(creatives["creative_id"])], creatives.set_index("creative_id")[self.creative_cats]])
        return self

    def _tx(self, d):
        X = d[self.tcat + self.tnum].copy()
        for c in self.tcat:
            X[c] = pd.Categorical(X[c].astype(str), categories=self.tlevels[c])
        return X

    # ---------- predict ----------
    def predict(self, df, budget_multiplier=1.0):
        d = self._design(df)
        lbr = d["lbr"].values + np.log(budget_multiplier)
        cold = ~d["ad_id"].isin(self.seen_ads).values
        out = df[["date", "ad_id", "audience_id", "creative_id"]].copy()
        for kpi in KPIS:
            hier, tree = self.m[kpi]
            parts = {"hier": hier.predict(d)}
            if tree is not None:
                parts["tree"] = tree.predict(self._tx(d))
            lv = d["ad_id"].map(self.level[kpi][0]).fillna(d["audience_id"].map(self.level[kpi][1])).values
            use = [parts[p] for p in self.blend[kpi] if p in parts]
            base = np.mean(use, axis=0)
            if "level" in self.blend[kpi]:
                ok = np.isfinite(lv) & ~cold
                base = np.where(ok, (np.sum(use, axis=0) + np.nan_to_num(lv)) / (len(use) + 1), base)
            out[kpi] = np.exp(base + np.log(d[f"season_{kpi}"].values / 100) + self.k[kpi] * lbr)
            if self.sigma:
                q = np.where(cold, self.sigma[kpi]["cold"], self.sigma[kpi]["warm"])
                out[kpi + "_lo"], out[kpi + "_hi"] = out[kpi] * np.exp(-q), out[kpi] * np.exp(q)
        out["new_ad"] = cold
        out["new_creative"] = ~d["creative_id"].isin(self.seen_creatives).values
        out["budget_extrapolated"] = (lbr > self.seen_lbr[1] + 1e-9) | (lbr < self.seen_lbr[0] - 1e-9)
        out["season_extrapolated"] = (d["season_cpm"].values > self.seen_season["cpm"][1] * 1.02)
        return out

    def calibrate(self, history, creatives, holdout_days=14, coverage=0.8):
        """Empirical bands from the last `holdout_days`, forecast by a model that never saw them."""
        cut = history["date"].max() - pd.Timedelta(days=holdout_days - 1)
        probe = Engine(self.cfg, self.level_days).fit(history[history["date"] < cut], creatives)
        held = history[(history["date"] >= cut) & (history["quality"] == "")]
        p = probe.predict(held)
        self.sigma = {}
        for kpi in KPIS:
            r = np.abs(np.log(held[kpi].values / p[kpi].values))
            cold = p["new_ad"].values
            q = lambda x: float(np.quantile(x, coverage)) if len(x) else float(np.quantile(r, coverage))
            self.sigma[kpi] = {"warm": q(r[~cold]), "cold": max(q(r[cold]), q(r[~cold]))}
        return self
