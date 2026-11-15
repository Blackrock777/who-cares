"""A world of advertisers that do not exist, built from sources that do.

Each simulated company is written to disk in its own column names with a config file, so the
engine reads it through exactly the same path a real customer would. The truth (who each audience
really is, whether it is warm, the true budget elasticity) is saved beside it for scoring.

Where every ingredient comes from (data/priors/priors.json holds the numbers):
  audience mix       Dirichlet around the real Ad Library reach mix of the vertical, with the
                     spread measured from real ads; warm audiences with the sourced warm effects
  cell CTR/CPM       Kaggle Facebook ads effects. Each company draws its own multipliers from their
                     uncertainty, so the inference never gets the exact numbers it assumes
  CTR level          WordStream 2025 vertical CTR, scaled for a sales objective, company spread
  CPM level          the kit's Meta Italy sales-objective median and IQR
  season             the kit's 2025 weekly index for the vertical, one year on (BF lift checked
                     against Lebesgue: kit 1.60-1.66x September vs 1.59-1.80x reported)
  budget             CPM rises with budget^k, k drawn around the shipped prior; some companies change
                     budgets, some never do (then k cannot be learned, and that is part of the test)
  fatigue, noise     ranges measured on the kit (late/first-week CTR ~0.7 over 13 weeks)
Scale ranges from a few euros a day (many zero-click days) to hundreds.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .population import load_priors

ROOT = Path(__file__).resolve().parents[1]
LEVERS = ["discount", "scarcity", "urgency", "social_proof", "benefit", "black_friday"]
FORMATS = ["image", "video", "carousel"]
SALES_VS_TRAFFIC_CTR = 0.62          # kit pooled CTR ~1.1% vs WordStream traffic ~1.6-1.8%


def make_company(seed, out_dir, priors=None, start="2026-08-17", end="2026-11-30", vertical=None, scale=None):
    p = priors or load_priors()
    rng = np.random.default_rng(seed)
    cells = p["cells"]
    vertical = vertical or rng.choice(list(p["verticals"]))
    v = p["verticals"][vertical]
    m = np.maximum(np.array([v["mean"][c] for c in cells]), 1e-4)
    m /= m.sum()
    scale = scale or rng.choice(["small", "medium", "large"], p=[0.3, 0.4, 0.3])
    n_aud = int(rng.integers(2, 7))
    n_cre = int(rng.integers(4, 16))
    dates = pd.date_range(start, end)

    # Cell multipliers: this company's truth, drawn from the uncertainty the inference assumes.
    R = {k: np.exp(np.array([p["cell_effects"][k]["log_mult"][c] for c in cells])
                   + rng.standard_normal(len(cells)) * np.array([p["cell_effects"][k]["log_sd"][c] for c in cells])) for k in ("ctr", "cpm")}
    wp = p["warm"]
    tsd = p["assumptions"]["targeting_noise_log_sd"]

    cpm_tab = pd.DataFrame(p["cpm_it_sales_monthly"])
    cpm0 = float(cpm_tab["cpm_mediano"].median()) * np.exp(rng.normal(0, np.log(cpm_tab["cpm_q3"] / cpm_tab["cpm_q1"]).median() / 2.7))
    ctr0 = v["wordstream_ctr_2025"] * SALES_VS_TRAFFIC_CTR * np.exp(rng.normal(0, 0.25))
    k_cpm, k_ctr = rng.normal(0.3, 0.1), rng.normal(-0.08, 0.05)
    phi = rng.uniform(0.01, 0.05)                         # CTR fatigue per week of ad age
    daily_budget = {"small": (5, 25), "medium": (30, 120), "large": (150, 600)}[scale]

    season = pd.read_csv(ROOT / "data" / "raw" / "benchmark_mercato_settimanale_2025.csv", parse_dates=["settimana_dal"])
    season = season[season["vertical"] == vertical]
    wk = (dates - pd.Timedelta(days=364))
    wk = wk - pd.to_timedelta(wk.weekday, unit="D")
    s_idx = season.set_index("settimana_dal").reindex(wk)
    s_ctr, s_cpm = s_idx["indice_ctr"].values / 100, s_idx["indice_cpm"].values / 100

    aud, truth = [], {}
    for i in range(n_aud):
        warm = i > 0 and rng.random() < wp["prior_probability"] * 1.5
        w = rng.dirichlet(m * v["kappa"])
        d = {k: (rng.normal(wp[f"{k}_log_effect"]["mean"], wp[f"{k}_log_effect"]["sd"]) if warm else 0.0) for k in ("ctr", "cpm")}
        e = {k: rng.normal(0, tsd[k]) for k in ("ctr", "cpm")}
        f_ex = rng.normal(wp["log_frequency_excess"]["warm"]["mean"], wp["log_frequency_excess"]["warm"]["sd"]) if warm else rng.normal(0, 0.01)
        b0 = float(np.round(rng.uniform(*daily_budget) * (0.5 if warm else 1.0), 2))
        change = rng.random() < 0.5
        t_change = int(rng.integers(20, len(dates) - 30)) if change else None
        mult = float(np.exp(rng.normal(0, 0.4))) if change else 1.0
        aid = f"AUD{i + 1}"
        aud.append(dict(id=aid, w=w, warm=warm, d=d, e=e, f_ex=f_ex, b0=b0, t_change=t_change, mult=mult))
        truth[aid] = {"share_female": float(w @ np.array([c.startswith("F") for c in cells])),
                      "mean_age": float(w @ np.array([p["age_centre"][c.split("|")[1]] for c in cells])),
                      "warm": bool(warm), "mix": dict(zip(cells, np.round(w, 4).tolist()))}

    cre = pd.DataFrame({"creative_key": [f"CR{j + 1}" for j in range(n_cre)], "lever": rng.choice(LEVERS, n_cre),
                        "format": rng.choice(FORMATS, n_cre)})
    lever_eff = {l: rng.normal(0, 0.15) for l in LEVERS}
    fmt_eff = {f: rng.normal(0, 0.1) for f in FORMATS}
    cre["effect"] = [lever_eff[l] + fmt_eff[f] + rng.normal(0, 0.15) for l, f in zip(cre["lever"], cre["format"])]

    ads, rows = [], []
    for a in aud:
        picks = rng.choice(n_cre, size=min(n_cre, int(rng.integers(2, 5))), replace=False)
        for j, ci in enumerate(picks):
            launch = 0 if j < 2 else int(rng.integers(10, len(dates) - 10))
            ads.append(dict(ad=f"{a['id']}-AD{j + 1}", aud=a, cre=cre.iloc[ci], launch=launch, own=rng.normal(0, 0.08)))
    mctr = (m * R["ctr"]).sum()
    mcpm = (m * R["cpm"]).sum()
    for t, day in enumerate(dates):
        wd = 1.0 + 0.04 * (day.weekday() >= 5)
        for a in aud:
            live = [x for x in ads if x["aud"] is a and x["launch"] <= t]
            if not live:
                continue
            budget = a["b0"] * (a["mult"] if a["t_change"] is not None and t >= a["t_change"] else 1.0)
            lbr = np.log(budget / a["b0"])
            cpm = cpm0 * (a["w"] * R["cpm"]).sum() / mcpm * np.exp(a["e"]["cpm"] + a["d"]["cpm"] + k_cpm * lbr) * s_cpm[t] * wd \
                * np.exp(rng.normal(0, 0.05))
            spend_total = budget * rng.uniform(0.93, 1.0)
            imp_total = spend_total / cpm * 1000
            ctr_true = []
            for x in live:
                age_w = (t - x["launch"]) / 7
                c = ctr0 * (a["w"] * R["ctr"]).sum() / mctr * np.exp(a["e"]["ctr"] + a["d"]["ctr"] + x["cre"]["effect"] + x["own"]
                                                                       - phi * age_w + k_ctr * lbr) * s_ctr[t] * np.exp(rng.normal(0, 0.08))
                ctr_true.append(c)
            share = np.array(ctr_true) ** 0.7 * rng.lognormal(0, 0.15, len(live))
            share /= share.sum()
            freq = np.exp(np.log(1.03) + a["f_ex"] + 0.05 * lbr + rng.normal(0, 0.005))
            for x, c, sh in zip(live, ctr_true, share):
                imp = int(rng.poisson(imp_total * sh))
                if imp == 0:
                    continue
                clicks = int(rng.poisson(imp * c / 100))
                rows.append({"day": day.date().isoformat(), "ad": x["ad"], "segment": a["id"], "asset": x["cre"]["creative_key"],
                             "imps": imp, "clk": min(clicks, imp), "cost": round(spend_total * sh, 2), "people": max(1, int(imp / freq)),
                             "daily_budget": round(budget, 2), "vertical": vertical})

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "daily.csv", index=False)
    cre[["creative_key", "lever", "format"]].to_csv(out / "assets.csv", index=False)
    pd.DataFrame([{"ad": x["ad"], "went_live": dates[x["launch"]].date().isoformat()} for x in ads]).to_csv(out / "ads.csv", index=False)
    season.to_csv(out / "season.csv", index=False)
    cfg = {"name": f"world_{seed}", "root": str(out.resolve()),
           "history": {"file": "daily.csv", "columns": {"date": "day", "ad_id": "ad", "audience_id": "segment", "creative_id": "asset",
                                                         "impressions": "imps", "clicks": "clk", "spend": "cost", "reach": "people",
                                                         "budget": "daily_budget"}},
           "ads": {"file": "ads.csv", "columns": {"ad_id": "ad", "launch_date": "went_live"}},
           "creatives": {"file": "assets.csv", "columns": {"creative_id": "creative_key"}, "categorical": ["lever", "format"]},
           "season": {"file": "season.csv", "week_start": "settimana_dal", "group": {"history_column": "vertical", "season_column": "vertical"},
                      "lag_days": 364, "kpis": {"ctr": "indice_ctr", "cpm": "indice_cpm"}, "smoothing": {"ctr": "none", "cpm": "pooled_unimodal"}},
           "priors": {"budget_elasticity": {"ctr": -0.1, "cpm": 0.3}, "prior_weight": 1.0},
           "blend": {"ctr": ["hier"], "cpm": ["hier", "tree", "level"]}, "encoder": "none", "archetypes": 3}
    (out / "config.json").write_text(json.dumps(cfg, indent=1))
    meta = {"seed": seed, "vertical": vertical, "scale": scale, "audiences": n_aud, "creatives": n_cre, "ads": len(ads), "rows": len(rows),
            "k_cpm": k_cpm, "k_ctr": k_ctr, "fatigue_per_week": phi, "ctr_level": ctr0, "cpm_level": cpm0,
            "budget_changes": int(sum(a["t_change"] is not None for a in aud)), "audiences_truth": truth,
            "zero_click_share": float(np.mean([r["clk"] == 0 for r in rows]))}
    (out / "truth.json").write_text(json.dumps(meta, indent=1))
    return out / "config.json", meta
