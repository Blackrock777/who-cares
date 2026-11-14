"""Load the BH Blasted data, remove the planted anomalies and build the feature table.

Every row is one ad on one day. The same function builds features for the history
(storico_giornaliero) and for the rows to predict (da_prevedere), so train and test
are guaranteed to be encoded identically.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

# Rows that are data-quality traps, found during exploration:
#  - 2026-10-14: every Coda Felice ad has 0 clicks (tracking outage)
#  - 2026-10-21: FGR ad set 1 spent 4x its daily budget
#  - 2026-11-09: NDL-AD15 has 0 clicks on a single day
TRAPS = [
    ("2026-10-14", "CDF"),
    ("2026-10-21", "FGR-AS1"),
    ("2026-11-09", "NDL-AD15"),
]

CAT_COLS = ["vertical", "adset_id", "asset_id", "leva", "formato", "adset_rank", "cta"]
NUM_COLS = [
    "days_since_launch", "log_days", "weekday", "weekend", "budget", "log_budget",
    "budget_ratio", "idx_cpm", "idx_ctr", "cpm_prior", "is_bf_week", "is_bf",
    "is_cyber", "is_event", "video_s", "discount_pct", "headline_len", "text_len",
    "hook_first2s", "logo_first", "talks_to_camera", "heavy_text", "discount_late",
    "timer", "person", "studio", "price_slash", "reviews", "black_bg",
]


def tag_assets(a: pd.DataFrame) -> pd.DataFrame:
    """Creative features from the text description. Works for the kit's assets and for a new one."""
    a = a.copy()
    d = a["descrizione_visual"].str.lower()
    h = a["headline"].str.lower()
    a["video_s"] = a["durata_video_s"].fillna(0)
    a["discount_pct"] = h.str.extract(r"-(\d+)%")[0].astype(float).fillna(0)
    a["headline_len"] = a["headline"].str.len()
    a["text_len"] = a["testo_principale"].str.len()
    a["cta"] = a["call_to_action"]
    a["hook_first2s"] = d.str.contains("primi 2 secondi|apre su|apre con|primi secondi").astype(int)
    a["logo_first"] = d.str.contains("logo").astype(int)
    a["talks_to_camera"] = d.str.contains("parla in camera").astype(int)
    a["heavy_text"] = d.str.contains("molto testo|molte righe|infografica|punti elenco|fitta").astype(int)
    a["discount_late"] = d.str.contains("compare (?:solo )?alla fine").astype(int)
    a["timer"] = d.str.contains("timer|countdown").astype(int)
    a["person"] = d.str.contains("ragazz|creator|proprietari|dermatolog|modell").astype(int)
    a["studio"] = d.str.contains("studio|sfondo bianco|sfondo neutro").astype(int)
    a["price_slash"] = d.str.contains("prezzo barrato").astype(int)
    a["reviews"] = d.str.contains("recension").astype(int)
    a["black_bg"] = d.str.contains("nera|sfondo nero").astype(int)
    # logo-first is a different thing from a hook in the first seconds
    a.loc[a["logo_first"] == 1, "hook_first2s"] = 0
    return a


def _assets() -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in (RAW / "asset_creativi").glob("*.csv")]
    return tag_assets(pd.concat(frames, ignore_index=True))


def _benchmark() -> pd.DataFrame:
    b = pd.read_csv(RAW / "benchmark_mercato_settimanale_2025.csv", parse_dates=["settimana_dal"])
    return b[["settimana_dal", "vertical", "indice_cpm", "indice_ctr"]]


def _cpm_prior() -> dict:
    c = pd.read_csv(RAW / "cpm_storici.csv")
    c = c[(c.piattaforma == "meta") & (c.paese == "IT") & (c.obiettivo == "vendite")]
    prior = dict(zip(c.mese, c.cpm_mediano))
    # November 2026 is not in the file: scale October 2026 by the 2025 Nov/Oct ratio
    prior["2026-11"] = prior["2026-10"] * prior["2025-11"] / prior["2025-10"]
    return prior


def build(df: pd.DataFrame, extra_assets: pd.DataFrame = None, extra_ads: pd.DataFrame = None) -> pd.DataFrame:
    """Attach features to a frame that has at least: data, ad_id, asset_id, adset_id,
    vertical, leva, formato, budget_giornaliero_adset.
    extra_assets / extra_ads let the app score a creative that is not in the kit."""
    df = df.copy()
    df["data"] = pd.to_datetime(df["data"])
    ads = pd.read_csv(RAW / "annunci.csv", parse_dates=["data_lancio"])
    adsets = pd.read_csv(RAW / "adset.csv")
    cal = pd.read_csv(RAW / "calendario.csv", parse_dates=["data"])
    assets = _assets()
    if extra_assets is not None:
        assets = pd.concat([assets, tag_assets(extra_assets)], ignore_index=True)
    if extra_ads is not None:
        ads = pd.concat([ads, extra_ads], ignore_index=True)

    df = df.merge(ads[["ad_id", "data_lancio"]], on="ad_id", how="left")
    df = df.merge(adsets[["adset_id", "budget_giornaliero_iniziale"]], on="adset_id", how="left")
    df = df.merge(cal[["data", "evento"]], on="data", how="left")
    df = df.merge(assets.drop(columns=["vertical", "leva", "formato", "data_lancio", "data_fine"]), on="asset_id", how="left")

    df["days_since_launch"] = (df["data"] - df["data_lancio"]).dt.days.clip(lower=0)
    df["log_days"] = np.log1p(df["days_since_launch"])
    df["weekday"] = df["data"].dt.weekday
    df["weekend"] = (df["weekday"] >= 5).astype(int)
    df["budget"] = df["budget_giornaliero_adset"].astype(float)
    df["log_budget"] = np.log(df["budget"])
    df["budget_ratio"] = df["budget"] / df["budget_giornaliero_iniziale"]
    df["adset_rank"] = df["adset_id"].str[-1]

    ev = df["evento"].fillna("")
    df["is_bf"] = (ev == "Black Friday").astype(int)
    df["is_cyber"] = (ev == "Cyber Monday").astype(int)
    df["is_event"] = (ev != "").astype(int)
    df["is_bf_week"] = ((df["data"] >= "2026-11-20") & (df["data"] <= "2026-11-29")).astype(int)

    # 2025 seasonal index, aligned on the same weekday 52 weeks earlier
    last_year = df["data"] - pd.Timedelta(days=364)
    week_start = last_year - pd.to_timedelta(last_year.dt.weekday, unit="D")
    bench = _benchmark()
    key = pd.DataFrame({"settimana_dal": week_start, "vertical": df["vertical"]})
    key = key.merge(bench, on=["settimana_dal", "vertical"], how="left")
    df["idx_cpm"] = key["indice_cpm"].values
    df["idx_ctr"] = key["indice_ctr"].values
    assert df["idx_cpm"].notna().all(), "benchmark week missing"

    prior = _cpm_prior()
    df["cpm_prior"] = df["data"].dt.strftime("%Y-%m").map(prior)

    for c in CAT_COLS:
        df[c] = df[c].astype("category")
    return df


def load_history() -> pd.DataFrame:
    h = pd.read_csv(RAW / "storico_giornaliero.csv")
    mask = pd.Series(False, index=h.index)
    for day, who in TRAPS:
        m = h["data"] == day
        if who.startswith(("NDL-AD", "CDF-AD", "FGR-AD")):
            m &= h["ad_id"] == who
        elif "-AS" in who:
            m &= h["adset_id"] == who
        else:
            m &= h["inserzionista_id"] == who
        mask |= m
    h = h[~mask].reset_index(drop=True)
    h = h[h["click"] > 0].reset_index(drop=True)
    return build(h)


def load_test() -> pd.DataFrame:
    return build(pd.read_csv(RAW / "da_prevedere.csv"))


if __name__ == "__main__":
    h = load_history()
    t = load_test()
    print("history rows", len(h), "test rows", len(t))
    print(h[["data", "ad_id", "ctr", "cpm", "days_since_launch", "idx_cpm", "idx_ctr", "hook_first2s", "heavy_text"]].head())
    print(_assets()[["asset_id", "hook_first2s", "logo_first", "talks_to_camera", "heavy_text", "discount_late", "timer", "person", "studio", "discount_pct"]].to_string())
