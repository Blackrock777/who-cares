"""Score a creative that does not exist yet: the 'push further' step of the brief.

Given a product vertical and a creative (lever, format, headline, text, CTA and a description
of the visual), the fitted model predicts CTR and CPM for every ad set of that advertiser over
the Black Week test window, and explains the prediction by flipping one creative feature at a
time (counterfactuals).
"""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from features import RAW, build, tag_assets

OUT = Path(__file__).resolve().parents[1] / "out"
TAGS = ["hook_first2s", "logo_first", "talks_to_camera", "heavy_text", "discount_late",
        "timer", "person", "studio", "price_slash", "reviews", "black_bg"]
TAG_LABELS = {
    "hook_first2s": "hook in the first 2 seconds", "logo_first": "logo before the hook",
    "talks_to_camera": "someone talks to camera", "heavy_text": "heavy text / infographic",
    "discount_late": "discount revealed only at the end", "timer": "timer or countdown",
    "person": "a person on screen", "studio": "studio / plain background",
    "price_slash": "crossed-out price", "reviews": "reviews shown", "black_bg": "black background",
}


def _model():
    return pickle.load(open(OUT / "model.pkl", "rb"))


def _frame(vertical, asset, launch="2026-11-23", start="2026-11-16", end="2026-11-30"):
    camp = pd.read_csv(RAW / "campagne.csv")
    camp = camp[camp["vertical"] == vertical].iloc[0]
    budget = pd.read_csv(RAW / "budget_giornaliero.csv")
    budget = budget[(budget["data"] >= start) & (budget["data"] <= end)]
    budget = budget[budget["adset_id"].str.startswith(camp["campaign_id"].split("-")[0])]
    rows = budget.rename(columns={"budget_giornaliero_eur": "budget_giornaliero_adset"}).copy()
    rows = rows[rows["data"] >= launch]
    rows["ad_id"] = "NEW-" + rows["adset_id"]
    rows["asset_id"] = asset["asset_id"]
    rows["campaign_id"] = camp["campaign_id"]
    rows["vertical"] = vertical
    rows["leva"] = asset["leva"]
    rows["formato"] = asset["formato"]
    rows["piattaforma"] = "meta"
    extra_ads = pd.DataFrame({"ad_id": rows["ad_id"].unique(), "data_lancio": pd.Timestamp(launch)})
    return build(rows, extra_assets=pd.DataFrame([asset]), extra_ads=extra_ads)


def score(vertical, leva, formato, durata, headline, testo, cta, descrizione, launch="2026-11-23"):
    asset = dict(asset_id="NEW-1", vertical=vertical, leva=leva, formato=formato,
                 durata_video_s=durata if formato == "video" else np.nan, headline=headline,
                 testo_principale=testo, call_to_action=cta, descrizione_visual=descrizione,
                 data_lancio=launch, data_fine=np.nan)
    model = _model()
    df = _frame(vertical, asset, launch)
    pred = model.predict(df)
    base = pd.concat([df[["data", "adset_id"]].reset_index(drop=True), pred.reset_index(drop=True)], axis=1)
    per_set = base.groupby("adset_id").agg(ctr=("ctr_pred", "mean"), ctr_lo=("ctr_lo", "mean"), ctr_hi=("ctr_hi", "mean"),
                                           cpm=("cpm_pred", "mean"), cpm_lo=("cpm_lo", "mean"), cpm_hi=("cpm_hi", "mean")).round(2)
    per_set["cpc"] = (per_set["cpm"] / (10 * per_set["ctr"])).round(2)
    tags = tag_assets(pd.DataFrame([asset])).iloc[0]
    # counterfactuals: flip each creative feature and see what the model does to CTR
    deltas = []
    for t in TAGS:
        flipped = df.copy()
        flipped[t] = 1 - int(tags[t])
        p2 = model.predict(flipped)
        d = (p2["ctr_pred"].mean() / pred["ctr_pred"].mean() - 1) * 100
        deltas.append(dict(feature=TAG_LABELS[t], present=bool(tags[t]), ctr_change_if_flipped=round(d, 1)))
    deltas = pd.DataFrame(deltas).sort_values("ctr_change_if_flipped", key=np.abs, ascending=False)
    daily = base.groupby("data")[["ctr_pred", "ctr_lo", "ctr_hi", "cpm_pred", "cpm_lo", "cpm_hi"]].mean().round(3)
    return per_set, tags[TAGS].astype(int), deltas, daily


if __name__ == "__main__":
    s, t, d, _ = score("beauty_skincare", "black_friday", "video", 12,
                       "Black Friday: -40% solo oggi",
                       "Tutta la linea a -40% fino a mezzanotte.", "Acquista ora",
                       "Creator in bagno parla in camera, apre con '-40% SOLO OGGI' nei primi 2 secondi, ritmo veloce.")
    print(s.to_string()); print(t.to_dict()); print(d.to_string(index=False))
