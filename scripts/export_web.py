"""Bundle everything the web app shows into web/data.js (window.DATA = {...}).

Forecasts are the official submission file out/predictions.csv, unchanged. Audiences come from
adsim.population (sourced priors + Bayesian inversion). The creative x audience matrix comes from
the adsim engine. The simulated-world proof comes from out/world/report.json when it exists.

  python scripts/export_web.py
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from adsim import Engine, load                                   # noqa: E402
from adsim.population import AudienceModel, audience_effects, load_priors     # noqa: E402

RAW, OUT = ROOT / "data" / "raw", ROOT / "out"


def r(x, n=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def creative_matrix(b, e):
    """Mean forecast CTR and CPM over 16-30 Nov for every creative of an advertiser in every one of
    its audiences, as if launched on 16 Nov (cold start: no ad-level history used)."""
    fut = b["future"]
    out = []
    for adv, g in fut.groupby("advertiser_id"):
        cr = b["creatives"]
        own = cr[cr["creative_id"].str.split("-").str[0] == adv.split("-")[0]]["creative_id"]
        base = g.drop_duplicates(["date", "audience_id"]).copy()
        rows = []
        for c in own:
            x = base.copy()
            x["creative_id"] = c
            x["ad_id"] = "LAB|" + x["audience_id"] + "|" + c
            x["age_days"] = (x["date"] - x["date"].min()).dt.days
            rows.append(x)
        x = pd.concat(rows)
        p = e.predict(x)
        m = p.groupby(["audience_id", "creative_id"]).agg(ctr=("ctr", "mean"), ctr_lo=("ctr_lo", "mean"), ctr_hi=("ctr_hi", "mean"),
                                                          cpm=("cpm", "mean")).reset_index()
        out += [{"audience": a, "creative": c, "ctr": r(ct), "ctr_lo": r(lo), "ctr_hi": r(hi), "cpm": r(cp, 3)}
                for a, c, ct, lo, hi, cp in m.itertuples(index=False)]
    return out


def main():
    pri = load_priors()
    b = load(ROOT / "configs" / "wevion_bighack.json")
    h = b["history"]
    vert = h.groupby("advertiser_id")["vertical"].first().to_dict()
    post = AudienceModel().infer_all(audience_effects(h), vert.get)

    adv = pd.read_csv(RAW / "inserzionisti.csv")
    camp = pd.read_csv(RAW / "campagne.csv")
    adsets = pd.read_csv(RAW / "adset.csv")
    ads = pd.read_csv(RAW / "annunci.csv")
    cr = pd.concat([pd.read_csv(f) for f in sorted((RAW / "asset_creativi").glob("*.csv"))])
    cal = pd.read_csv(RAW / "calendario.csv").fillna("")
    budget = pd.read_csv(RAW / "budget_giornaliero.csv")
    pred = pd.read_csv(OUT / "predictions.csv")
    hyp = json.loads((OUT / "audiences.json").read_text())
    fp = pd.read_csv(OUT / "adset_fingerprint.csv").set_index("adset_id")
    dec = json.loads((OUT / "decisions.json").read_text())
    val = pd.read_csv(OUT / "validation.csv")

    hist = pd.read_csv(RAW / "storico_giornaliero.csv")
    daily_ad = {a: {"d": g["data"].tolist(), "ctr": g["ctr"].round(4).tolist(), "cpm": g["cpm"].round(3).tolist(),
                    "imp": g["impression"].tolist(), "clk": g["click"].tolist()} for a, g in hist.sort_values("data").groupby("ad_id")}
    daily_set = {}
    for s, g in hist.groupby("adset_id"):
        x = g.groupby("data")[["impression", "click", "spesa", "copertura"]].sum().reset_index()
        daily_set[s] = {"d": x["data"].tolist(), "ctr": (x.click / x.impression * 100).round(4).tolist(),
                        "cpm": (x.spesa / x.impression * 1000).round(3).tolist(), "spend": x.spesa.round(2).tolist()}
    fc = {a: {"d": g["data"].tolist(), "ctr": g["ctr_pred"].tolist(), "ctr_lo": g["ctr_lo"].tolist(), "ctr_hi": g["ctr_hi"].tolist(),
              "cpm": g["cpm_pred"].tolist(), "cpm_lo": g["cpm_lo"].tolist(), "cpm_hi": g["cpm_hi"].tolist(),
              "budget": g["budget_giornaliero_adset"].tolist(), "cold": int(g["cold_start"].max())}
          for a, g in pred.sort_values("data").groupby("ad_id")}

    e = Engine(b["cfg"]).calibrate(h, b["creatives"]).fit(h, b["creatives"])
    lab = creative_matrix(b, e)

    sets = []
    for s in adsets.itertuples():
        f = fp.loc[s.adset_id]
        hy = hyp.get(s.adset_id, {})
        bud = budget[budget.adset_id == s.adset_id].sort_values("data")
        sets.append({"id": s.adset_id, "campaign": s.campaign_id, "advertiser": s.campaign_id.split("-")[0], "name": s.adset_name,
                     "optimisation": s.ottimizzazione, "base_budget": float(s.budget_giornaliero_iniziale),
                     "budget": {"d": bud["data"].tolist(), "eur": bud["budget_giornaliero_eur"].round(2).tolist()},
                     "fingerprint": {"ctr": r(f["ctr_%"]), "cpm": r(f["cpm_eur"], 3), "cpc": r(f["cpc_eur"], 3), "frequency": r(f["frequency"]),
                                     "fatigue": r(f["fatigue_late_vs_first_week"], 3), "impressions": int(f["impressions"]), "profile": f["profile"]},
                     "behaviour": {"name": hy.get("name"), "who": hy.get("who"), "alternative": hy.get("alternative"),
                                   "implication": hy.get("implication"), "confidence": hy.get("confidence")},
                     "population": post.get(s.adset_id), "history": daily_set.get(s.adset_id)})

    data = {
        "generated": pd.Timestamp.now().isoformat(timespec="minutes"),
        "advertisers": [{"id": x.inserzionista_id, "name": x.nome, "vertical": x.vertical, "description": x.descrizione,
                         "campaign": camp.loc[camp.inserzionista_id == x.inserzionista_id, "campaign_id"].iloc[0]} for x in adv.itertuples()],
        "adsets": sets,
        "ads": [{"id": a.ad_id, "adset": a.adset_id, "creative": a.asset_id, "name": a.ad_name, "launch": a.data_lancio,
                 "end": a.data_fine if isinstance(a.data_fine, str) else None} for a in ads.itertuples()],
        "creatives": [{"id": c.asset_id, "vertical": c.vertical, "lever": c.leva, "format": c.formato,
                       "video_s": None if pd.isna(c.durata_video_s) else float(c.durata_video_s), "headline": c.headline,
                       "body": c.testo_principale, "cta": c.call_to_action, "visual": c.descrizione_visual} for c in cr.itertuples()],
        "calendar": cal[cal.evento != ""][["data", "evento", "periodo"]].to_dict("records"),
        "history": daily_ad, "forecast": fc, "lab": lab,
        "decisions": dec,
        "validation": val.to_dict("records"),
        "engine": {"k_cpm": r(e.k["cpm"]), "k_ctr": r(e.k["ctr"]), "ctr_mode": e.ctr_mode, "interval": e.interval_status},
        "priors": {k: pri[k] for k in ("cells", "ages", "age_centre", "population_it_millions", "verticals", "cell_effects",
                                       "kaggle_effects", "bf_week_cpm_vs_september", "cross_checks", "warm", "assumptions")},
    }
    import os
    sr = Path(os.environ.get("STUDIO_RUNS", OUT / "studio" / "runs.json"))
    data["studio"] = json.loads(sr.read_text()) if sr.exists() else {}
    data["studio_briefs"] = {k: v for k, v in json.loads((ROOT / "configs" / "studio" / "briefs.json").read_text()).items() if not k.startswith("_")}
    wr = OUT / "world" / "report.json"
    if wr.exists():
        data["world"] = json.loads(wr.read_text())
        au = OUT / "world" / "audiences.csv"
        if au.exists():
            data["world_audiences"] = pd.read_csv(au)[["vertical", "female_true", "female_est", "female_prior", "age_true", "age_est",
                                                        "age_prior", "warm_true", "p_warm"]].round(3).to_dict("records")
    js = "window.DATA = " + json.dumps(data, ensure_ascii=False, default=lambda o: None if o is None else str(o)).replace("NaN", "null") + ";\n"
    (ROOT / "web" / "data.js").write_text(js)
    print(f"wrote web/data.js ({len(js) / 1e6:.2f} MB): {len(sets)} audiences, {len(fc)} forecast ads, {len(lab)} lab cells")


if __name__ == "__main__":
    main()
