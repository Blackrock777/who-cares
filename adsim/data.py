"""Turn any customer's tables into the canonical ad-day frame described in docs/BUILD_BRIEF.md.

Nothing in this file knows a brand, a date, a language or an ID format. The config maps columns.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _read(root, spec):
    files = sorted(root.glob(spec["glob"])) if "glob" in spec else [root / spec["file"]]
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def _canon(df, columns):
    return df.rename(columns={v: k for k, v in columns.items()})


def _season(cfg, root):
    """Optional market index, 100-based. Returns {kpi: frame(week_start, group, value)}."""
    s = cfg.get("season")
    if not s:
        return None
    b = pd.read_csv(root / s["file"], parse_dates=[s["week_start"]]).rename(columns={s["week_start"]: "week_start"})
    gcol = s.get("group", {}).get("season_column")
    b["group"] = b[gcol].astype(str) if gcol else "all"
    out = {}
    for kpi, col in s["kpis"].items():
        t = b[["week_start", "group", col]].rename(columns={col: "value"}).copy()
        mode = s.get("smoothing", {}).get(kpi, "none")
        if mode in ("pooled", "pooled_unimodal"):
            t["value"] = t.groupby("week_start")["value"].transform("mean")
        if mode in ("unimodal", "pooled_unimodal"):
            from sklearn.isotonic import IsotonicRegression
            parts = []
            for _, g in t.groupby("group"):
                g = g.sort_values("week_start").copy()
                y, x, pk = g["value"].values.astype(float), np.arange(len(g)), int(g["value"].values.argmax())
                up = IsotonicRegression(increasing=True).fit_transform(x[:pk + 1], y[:pk + 1])
                dn = IsotonicRegression(increasing=False).fit_transform(x[pk:], y[pk:])
                g["value"] = np.concatenate([up, dn[1:]])
                parts.append(g)
            t = pd.concat(parts)
        out[kpi] = t
    return out


def flag_anomalies(h):
    """Rule-based quality flags; nothing is listed by hand.

    zero_clicks_improbable: zero clicks where the ad's own typical rate made that a <0.1% event.
    spend_over_budget: an audience's ads together spent more than 1.5x its daily budget.
    """
    h = h.copy()
    h["quality"] = ""
    rate = h.groupby("ad_id").apply(lambda g: g.clicks.sum() / max(g.impressions.sum(), 1)).rename("r")
    expected = h["impressions"] * h["ad_id"].map(rate)
    h.loc[(h["clicks"] == 0) & (np.exp(-expected) < 1e-3), "quality"] = "zero_clicks_improbable"
    if "budget" in h:
        tot = h.groupby(["date", "audience_id"])["spend"].transform("sum")
        h.loc[(tot > 1.5 * h["budget"]) & (h["quality"] == ""), "quality"] = "spend_over_budget"
    h.loc[(h["clicks"] <= 0) & (h["quality"] == ""), "quality"] = "zero_clicks"
    return h


def load(config_path):
    cfg = json.loads(Path(config_path).read_text())
    root = Path(cfg["root"])
    if not root.is_absolute():
        root = (Path(config_path).resolve().parent.parent / root)
    hist = _canon(_read(root, cfg["history"]), cfg["history"]["columns"])
    fut = _canon(_read(root, cfg["future"]), cfg["future"]["columns"]) if cfg.get("future") else None
    cr = _canon(_read(root, cfg["creatives"]), cfg["creatives"]["columns"]) if cfg.get("creatives") else None
    ads = _canon(_read(root, cfg["ads"]), cfg["ads"]["columns"]) if cfg.get("ads") else None
    aud = _canon(_read(root, cfg["audiences"]), cfg["audiences"]["columns"]) if cfg.get("audiences") else None
    season = _season(cfg, root)
    gcol = (cfg.get("season") or {}).get("group", {}).get("history_column")
    lag = (cfg.get("season") or {}).get("lag_days", 0)
    missing = []

    def finish(df, is_history):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        for c in ["ad_id", "audience_id", "creative_id"]:
            df[c] = df[c].astype(str)
        df["advertiser_id"] = df["advertiser_id"].astype(str) if "advertiser_id" in df else "all"
        if ads is not None:
            df = df.merge(ads[["ad_id", "launch_date"]].assign(launch_date=lambda a: pd.to_datetime(a.launch_date)), on="ad_id", how="left")
        else:
            df["launch_date"] = pd.NaT
        first_seen = pd.concat([hist.assign(date=pd.to_datetime(hist["date"]))[["ad_id", "date"]], df[["ad_id", "date"]]]).groupby("ad_id")["date"].min()
        df["launch_date"] = df["launch_date"].fillna(df["ad_id"].map(first_seen))
        df["age_days"] = (df["date"] - df["launch_date"]).dt.days.clip(lower=0)
        if "budget" not in df:
            df["budget"] = 1.0
            missing.append("budget")
        if aud is not None and "base_budget" in aud:
            df = df.merge(aud[["audience_id", "base_budget"]].astype({"audience_id": str}), on="audience_id", how="left")
        else:
            base = hist.assign(a=hist["audience_id"].astype(str)).groupby("a")["budget"].median() if "budget" in hist else None
            df["base_budget"] = df["audience_id"].map(base) if base is not None else 1.0
        df["base_budget"] = df["base_budget"].fillna(df["budget"])
        df["lbr"] = np.log(df["budget"].astype(float) / df["base_budget"].astype(float))
        for kpi in ("ctr", "cpm"):
            df[f"season_{kpi}"] = 100.0
            if season and kpi in season:
                ref = df["date"] - pd.Timedelta(days=lag)
                wk = ref - pd.to_timedelta(ref.dt.weekday, unit="D")
                key = pd.DataFrame({"week_start": wk.values, "group": df[gcol].astype(str).values if gcol else "all"})
                val = key.merge(season[kpi], on=["week_start", "group"], how="left")["value"].values
                if np.isnan(val).any():
                    raise ValueError(f"Season index does not cover all dates for {kpi}.")
                df[f"season_{kpi}"] = val
        if is_history:
            df["ctr"] = df["clicks"] / df["impressions"] * 100
            df["cpm"] = df["spend"] / df["impressions"] * 1000
            df["frequency"] = df["impressions"] / df["reach"] if "reach" in df else np.nan
            df = flag_anomalies(df)
        return df

    if not season:
        missing.append("season index")
    if cr is None:
        missing.append("creative text")
    history = finish(hist, True)
    if cr is None:
        cr = pd.DataFrame({"creative_id": sorted(history["creative_id"].unique())})
    return {"cfg": cfg, "history": history, "future": finish(fut, False) if fut is not None else None,
            "creatives": cr.assign(creative_id=lambda c: c.creative_id.astype(str)),
            "missing_optional_inputs": sorted(set(missing))}
