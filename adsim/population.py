"""Who is behind an ad set's numbers: a Bayesian answer with its uncertainty stated.

The unknown is the ad set's mix over 10 cells (gender x age band). The prior is the reach mix of
real Italian ads in the same vertical (Meta Ad Library), with a spread estimated from how much
those real ads differ from one another. The likelihood links the mix to what we observe: an ad
set's click rate and price relative to its advertiser, after removing creative, ad age and season.
Each cell's relative click rate and price come from a public Facebook ads dataset; those
multipliers are uncertain, so every posterior draw also draws them.

Audience temperature. Retargeted ("warm") audiences behave differently for reasons unrelated to
age or gender: the pool is small, so frequency rises, and the auction is pricier. Ignoring this
would read a retargeting ad set as "older women" because both raise CTR and CPM. So the model also
carries a latent warm/cold switch, informed mainly by frequency relative to the advertiser's other
audiences, with the warm effect on CTR and CPM drawn from wide priors (sources disagree on CTR).

What it can and cannot tell you: two observed numbers per ad set cannot pin down ten shares. The
output is a posterior over the whole mix, a summary in two dimensions (share of women, mean age),
and how far the data moved each of those away from the prior. When it barely moved, the answer is
"the typical audience of this vertical", and the tool says so.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

PRIORS = Path(__file__).resolve().parents[1] / "data" / "priors" / "priors.json"


def load_priors(path=PRIORS):
    return json.loads(Path(path).read_text())


def audience_effects(history, min_rows=10):
    """Per advertiser and audience: log CTR and log CPM relative to the advertiser's average
    audience, holding creative, ad age, weekday and season fixed. Returns one row per audience."""
    h = history[(history.get("quality", "") == "") & (history["impressions"] > 0)].copy()
    out = []
    for adv, g in h.groupby("advertiser_id"):
        if g["audience_id"].nunique() < 2:
            for a, ga in g.groupby("audience_id"):
                out.append({"advertiser_id": adv, "audience_id": a, "y_ctr": 0.0, "y_cpm": 0.0, "y_freq": 0.0, "se_ctr": 1.0, "se_cpm": 1.0,
                            "impressions": float(ga["impressions"].sum()), "single_audience": True})
            continue
        freq = {}
        if "reach" in g and g["reach"].notna().all() and (g["reach"] > 0).all():
            f = np.log(g.groupby("audience_id")["impressions"].sum() / g.groupby("audience_id")["reach"].sum())
            freq = (f - f.median()).to_dict()                                   # median: robust to the one warm audience
        X = pd.get_dummies(g[["audience_id", "creative_id"]].astype(str)).astype(float)
        X["log_age"] = np.log1p(g["age_days"].values)
        X = pd.concat([X, pd.get_dummies(g["date"].dt.weekday.astype(str), prefix="wd").astype(float)], axis=1)
        w = g["impressions"].values / g["impressions"].mean()
        season = {k: np.log(g[f"season_{k}"].values / 100) if f"season_{k}" in g else 0.0 for k in ("ctr", "cpm")}
        res = {}
        for kpi, y in (("ctr", np.log((g["clicks"].values + 0.5) / g["impressions"].values * 100)),
                       ("cpm", np.log(np.maximum(g["spend"].values, 1e-6) / g["impressions"].values * 1000))):
            ok = np.ones(len(g), bool) if kpi == "ctr" else g["spend"].values > 0
            m = Ridge(alpha=1.0).fit(X[ok], (y - season[kpi])[ok], sample_weight=w[ok])
            coef = pd.Series(m.coef_, X.columns).filter(like="audience_id_")
            coef.index = coef.index.str.replace("audience_id_", "", regex=False)
            imp = g.groupby("audience_id")["impressions"].sum().reindex(coef.index)
            coef = coef - np.average(coef, weights=imp)                       # relative to the advertiser's average audience
            resid = (y - season[kpi])[ok] - m.predict(X[ok])
            n = g.loc[ok].groupby("audience_id").size().reindex(coef.index)
            res[kpi] = (coef, np.std(resid) / np.sqrt(np.maximum(n, 1)))
        for a in res["ctr"][0].index:
            out.append({"advertiser_id": adv, "audience_id": a, "y_ctr": float(res["ctr"][0][a]), "y_cpm": float(res["cpm"][0][a]),
                        "y_freq": float(freq.get(a, 0.0)),
                        "se_ctr": float(res["ctr"][1][a]), "se_cpm": float(res["cpm"][1][a]),
                        "impressions": float(g.loc[g["audience_id"] == a, "impressions"].sum()), "single_audience": False})
    return pd.DataFrame(out)


class AudienceModel:
    def __init__(self, priors=None, draws=40000, seed=0, targeting_sd=None):
        self.p = priors or load_priors()
        self.cells = self.p["cells"]
        self.draws, self.seed = draws, seed
        self.tsd = targeting_sd or self.p["assumptions"]["targeting_noise_log_sd"]
        self.age = np.array([self.p["age_centre"][c.split("|")[1]] for c in self.cells])
        self.female = np.array([c.startswith("F") for c in self.cells], float)

    def prior(self, vertical):
        v = self.p["verticals"].get(vertical)
        if v is None:                                                      # unknown vertical: Italian Meta population
            pop = np.array([self.p["population_it_millions"][c] for c in self.cells])
            return pop / pop.sum(), 8.0
        m = np.array([v["mean"][c] for c in self.cells])
        m = np.maximum(m, 1e-4)
        return m / m.sum(), float(v["kappa"])

    def _mult(self, rng, n):
        """Cell multipliers for CTR and CPM, one draw per posterior sample (their uncertainty is real)."""
        out = {}
        for kpi in ("ctr", "cpm"):
            mu = np.array([self.p["cell_effects"][kpi]["log_mult"][c] for c in self.cells])
            sd = np.array([self.p["cell_effects"][kpi]["log_sd"][c] for c in self.cells])
            out[kpi] = np.exp(mu + rng.standard_normal((n, len(mu))) * sd)
        return out

    def infer(self, vertical, y_ctr, y_cpm, se_ctr=0.0, se_cpm=0.0, y_freq=None):
        rng = np.random.default_rng(self.seed)
        m, kappa = self.prior(vertical)
        n = self.draws
        W = rng.dirichlet(m * kappa, n)
        R = self._mult(rng, n)
        wp = self.p["warm"]
        warm = rng.random(n) < wp["prior_probability"]
        delta = {k: rng.normal(wp[f"{k}_log_effect"]["mean"], wp[f"{k}_log_effect"]["sd"], n) for k in ("ctr", "cpm")}
        ll = np.zeros(n)
        for kpi, y, se in (("ctr", y_ctr, se_ctr), ("cpm", y_cpm, se_cpm)):
            pred = np.log((W * R[kpi]).sum(1)) - np.log((m * R[kpi]).sum(1)) + warm * delta[kpi]
            s2 = self.tsd[kpi] ** 2 + se ** 2
            ll -= 0.5 * (y - pred) ** 2 / s2
        if y_freq is not None:
            fc, fw = wp["log_frequency_excess"]["cold"], wp["log_frequency_excess"]["warm"]
            mu, sd = np.where(warm, fw["mean"], fc["mean"]), np.where(warm, fw["sd"], fc["sd"])
            ll += -0.5 * ((y_freq - mu) / sd) ** 2 - np.log(sd)
        wt = np.exp(ll - ll.max())
        wt /= wt.sum()
        return Posterior(self, W, wt, m, warm)

    def infer_all(self, effects, vertical_of):
        rows = {}
        for r in effects.itertuples():
            post = self.infer(vertical_of(r.advertiser_id), r.y_ctr, r.y_cpm, r.se_ctr, r.se_cpm, getattr(r, "y_freq", None))
            rows[r.audience_id] = post.summary() | {"advertiser_id": r.advertiser_id, "observed": {
                "ctr_vs_advertiser": round(float(np.exp(r.y_ctr)), 3), "cpm_vs_advertiser": round(float(np.exp(r.y_cpm)), 3),
                "frequency_vs_advertiser": round(float(np.exp(getattr(r, "y_freq", 0.0))), 3)},
                "single_audience": bool(r.single_audience)}
        return rows


class Posterior:
    def __init__(self, model, W, wt, prior_mean, warm=None):
        self.m, self.W, self.wt, self.prior_mean = model, W, wt, prior_mean
        self.warm = np.zeros(len(wt), bool) if warm is None else warm

    def _q(self, x, qs):
        o = np.argsort(x)
        c = np.cumsum(self.wt[o])
        return [float(x[o][min(np.searchsorted(c, q), len(x) - 1)]) for q in qs]

    def summary(self):
        f = self.W @ self.m.female
        a = self.W @ self.m.age
        mean = self.wt @ self.W
        prior_f_sd, prior_a_sd = f.std(), a.std()                          # prior draws are uniformly weighted
        post = lambda x: (float(self.wt @ x), float(np.sqrt(self.wt @ (x - self.wt @ x) ** 2)))
        fm, fs = post(f)
        am, as_ = post(a)
        ess = float(1.0 / np.sum(self.wt ** 2))
        cells = {c: {"share": round(float(mean[i]), 4), "prior": round(float(self.prior_mean[i]), 4),
                     "p10": round(self._q(self.W[:, i], [0.1])[0], 4), "p90": round(self._q(self.W[:, i], [0.9])[0], 4)}
                 for i, c in enumerate(self.m.cells)}
        info = {"share_female": round(float(1 - fs / prior_f_sd), 3), "mean_age": round(float(1 - as_ / prior_a_sd), 3)}
        shift = {"share_female": round(float((fm - f.mean()) / prior_f_sd), 2), "mean_age": round(float((am - a.mean()) / prior_a_sd), 2)}
        pw = float(self.wt @ self.warm)
        return {"cells": cells, "p_warm": round(pw, 3),
                "temperature": "warm (retargeting-like)" if pw >= 0.7 else "cold (prospecting)" if pw <= 0.3 else "unclear",
                "share_female": {"mean": round(fm, 3), "p10": round(self._q(f, [0.1])[0], 3), "p90": round(self._q(f, [0.9])[0], 3),
                                 "prior": round(float(self.prior_mean @ self.m.female), 3)},
                "mean_age": {"mean": round(am, 1), "p10": round(self._q(a, [0.1])[0], 1), "p90": round(self._q(a, [0.9])[0], 1),
                             "prior": round(float(self.prior_mean @ self.m.age), 1)},
                "information_gain": info, "shift_in_prior_sd": shift, "effective_draws": round(ess),
                "label": label(fm, am, info, shift)}


def label(female, age, info, shift, threshold=0.5):
    g = "mostly women" if female >= 0.65 else "mostly men" if female <= 0.35 else "women and men"
    lo = int(max(18, round(age - 9, -0) // 5 * 5))
    a = f"around {lo}-{lo + 15}"
    moved = []
    if abs(shift["share_female"]) >= threshold:
        moved.append("more women than the vertical" if shift["share_female"] > 0 else "more men than the vertical")
    if abs(shift["mean_age"]) >= threshold:
        moved.append("older than the vertical" if shift["mean_age"] > 0 else "younger than the vertical")
    conf = "data-led" if max(abs(v) for v in shift.values()) >= 1 else "partly data-led" if moved else "mostly the vertical prior"
    return {"headline": f"{g}, {a}", "versus_vertical": moved or ["close to the vertical's typical audience"], "confidence": conf}
