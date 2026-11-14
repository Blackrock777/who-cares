"""Score a creative that does not exist yet: the 'push further' step of the brief.

Given a product vertical and a creative (lever, format, headline, text, CTA and a description
of the visual), the fitted model predicts CTR and CPM for every ad set of that advertiser over
the Black Week test window, and explains the prediction by flipping one creative feature at a
time (counterfactuals).
"""
import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from features import RAW, build, tag_assets
from model import fit_production, input_fingerprint

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


@lru_cache(maxsize=2)
def _cached_model(fingerprint):
    path = OUT / "model.pkl"
    if path.exists():
        try:
            with path.open("rb") as handle:
                fitted = pickle.load(handle)
            if getattr(fitted, "fingerprint", None) == fingerprint:
                return fitted
        except (OSError, ValueError, EOFError, pickle.UnpicklingError, AttributeError, ImportError):
            pass
    # Fresh checkouts intentionally omit the local pickle; build from the supplied kit.
    fitted = fit_production()
    OUT.mkdir(exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(fitted, handle)
    return fitted


def _model():
    return _cached_model(input_fingerprint())


def _frame(vertical, asset, launch="2026-11-23", start="2026-11-16", end="2026-11-30"):
    camp = pd.read_csv(RAW / "campagne.csv")
    camp = camp[camp["vertical"] == vertical]
    if camp.empty:
        raise ValueError("Choose one of the three supplied verticals.")
    if not pd.Timestamp(start) <= pd.Timestamp(launch) <= pd.Timestamp(end):
        raise ValueError("Launch date must be between 16 and 30 November 2026.")
    camp = camp.iloc[0]
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
    if not headline.strip() or not descrizione.strip():
        raise ValueError("Provide a headline and a visual description.")
    if leva not in {"black_friday", "urgency", "scarcity"} or formato not in {"video", "immagine", "carosello"}:
        raise ValueError("Unknown lever or format.")
    if formato == "video" and not 0 < durata <= 60:
        raise ValueError("Video duration must be 1-60 seconds.")
    asset = dict(asset_id="NEW-1", vertical=vertical, leva=leva, formato=formato,
                 durata_video_s=durata if formato == "video" else np.nan, headline=headline,
                 testo_principale=testo, call_to_action=cta, descrizione_visual=descrizione,
                 data_lancio=launch, data_fine=np.nan)
    model = _model()
    df = _frame(vertical, asset, launch)
    pred = model.predict(df)
    base = pd.concat([df[["data", "adset_id"]].reset_index(drop=True), pred.reset_index(drop=True)], axis=1)
    per_set = base.groupby("adset_id", observed=True).agg(ctr=("ctr_pred", "mean"), ctr_lo=("ctr_lo", "mean"), ctr_hi=("ctr_hi", "mean"),
                                           cpm=("cpm_pred", "mean"), cpm_lo=("cpm_lo", "mean"), cpm_hi=("cpm_hi", "mean"))
    base["clicks_per_eur"] = 10 * base.ctr_pred / base.cpm_pred
    per_set["cpc"] = 1 / base.groupby("adset_id", observed=True).clicks_per_eur.mean()
    per_set = per_set.round(3)
    tags = tag_assets(pd.DataFrame([asset])).iloc[0]
    # counterfactuals: flip each creative feature and see what the model does to CTR
    deltas = []
    for t in TAGS:
        flipped = df.copy()
        flipped[t] = 1 - int(tags[t])
        if t == "logo_first" and not tags[t]:
            flipped["hook_first2s"] = 0
        if t == "talks_to_camera" and not tags[t]:
            flipped["person"] = 1
        if t == "person" and tags[t]:
            flipped["talks_to_camera"] = 0
        p2 = model.predict(flipped)
        for adset in df.adset_id.unique():
            mask = df.adset_id == adset
            d = (p2.loc[mask, "ctr_pred"].mean() / pred.loc[mask, "ctr_pred"].mean() - 1) * 100
            deltas.append(dict(adset_id=adset, feature=TAG_LABELS[t], present=bool(tags[t]), ctr_change_if_flipped=round(d, 1)))
    deltas = pd.DataFrame(deltas).sort_values("ctr_change_if_flipped", key=np.abs, ascending=False)
    daily = base.groupby("data")[["ctr_pred", "ctr_lo", "ctr_hi", "cpm_pred", "cpm_lo", "cpm_hi"]].mean().round(3)
    return per_set, tags[TAGS].astype(int), deltas, daily


if __name__ == "__main__":
    s, t, d, _ = score("beauty_skincare", "black_friday", "video", 12,
                       "Black Friday: -40% solo oggi",
                       "Tutta la linea a -40% fino a mezzanotte.", "Acquista ora",
                       "Creator in bagno parla in camera, apre con '-40% SOLO OGGI' nei primi 2 secondi, ritmo veloce.")
    print(s.to_string()); print(t.to_dict()); print(d.to_string(index=False))
