"""Turn Meta Ad Library records into a modelling dataset with a large, leak-free test split.

Input: the JSON the official Ad Library API returns (`ads_archive`), one object per ad, saved as a
JSON list or JSON-lines file. The same field names are used by Meta's own connector. Fields read:
  id, page_id, page_name, ad_creative_bodies, ad_creative_link_titles,
  ad_creative_link_descriptions, ad_creative_link_captions, ad_delivery_start_time,
  ad_delivery_stop_time, publisher_platforms, languages, eu_total_reach, target_ages,
  target_gender, age_country_gender_reach_breakdown

What this data can and cannot test
  * It has NO clicks, CTR, CPM or spend for commercial ads. It cannot validate the KPI forecasts.
  * It has, for ads delivered in the EU: how long each ad ran, how many people it reached, and the
    age x gender x country split of that reach. Those are real outcomes of delivery.
  * So it supports three tests: (1) does the creative encoder predict which ads keep running,
    (2) does it predict reach, (3) does it predict who an ad reaches (age and gender shares).
    Longevity and reach reflect the advertiser's budget and choices as well as ad quality; they
    are weak labels and are never reported as performance.

Split: by time and by creative. Ads are grouped by normalised text so the same copy never sits on
both sides; groups are ordered by first launch date; the oldest `train_share` of groups train and
the rest test. Default is 40% train / 60% test, because the purpose is to find where the model fails.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

AGE_BANDS = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]


def _records(path):
    text = Path(path).read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return json.loads(text)
    if text.startswith("{") and '"data"' in text[:200]:
        return json.loads(text)["data"]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _join(v):
    return " ".join(dict.fromkeys(x.strip() for x in (v or []) if x and x.strip())) if isinstance(v, list) else (v or "")


def _find(obj, names, depth=0):
    """First non-empty value stored under any of `names`, searching nested dicts (scraper output nests details)."""
    if isinstance(obj, dict):
        for n in names:
            if obj.get(n) not in (None, "", [], {}):
                return obj[n]
        if depth < 4:
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    hit = _find(v, names, depth + 1)
                    if hit not in (None, "", [], {}):
                        return hit
    elif isinstance(obj, list) and depth < 4:
        for v in obj[:5]:
            hit = _find(v, names, depth + 1)
            if hit not in (None, "", [], {}):
                return hit
    return None


def _text(v):
    if isinstance(v, dict):
        v = v.get("text") or v.get("markup") or ""
    v = (v or "").strip()
    return "" if v.startswith("{{") else v              # template placeholders of catalogue ads carry no copy


def _day(v):
    if v in (None, "", 0):
        return None
    if isinstance(v, (int, float)) or str(v).isdigit():
        return pd.to_datetime(int(v), unit="s").strftime("%Y-%m-%d")
    return str(v)[:10]


def from_scraper(records):
    """Map items from a third-party Ad Library scraper (Apify actors) onto the official API field names.

    Field names vary by actor and change over time, so values are looked up by several known names
    at any nesting level. Anything not found stays empty; `summary.json` reports how many ads have
    text and reach so a silent mapping failure is visible.
    """
    out = []
    for r in records:
        snap = r.get("snapshot") or {}
        cards = snap.get("cards") or []
        bodies = [_text(snap.get("body"))] + [_text(c.get("body")) for c in cards]
        titles = [_text(snap.get("title"))] + [_text(c.get("title")) for c in cards]
        descs = [_text(snap.get("link_description"))] + [_text(c.get("link_description")) for c in cards]
        fmt = snap.get("display_format") or ("VIDEO" if snap.get("videos") else "IMAGE" if snap.get("images") else "")
        out.append({"id": str(r.get("ad_archive_id") or r.get("adArchiveID") or r.get("ad_id") or r.get("id")),
                    "page_id": str(r.get("page_id") or snap.get("page_id") or ""), "page_name": r.get("page_name") or snap.get("page_name") or "",
                    "ad_creative_bodies": [b for b in bodies if b], "ad_creative_link_titles": [t for t in titles if t],
                    "ad_creative_link_descriptions": [d for d in descs if d], "ad_creative_link_captions": [snap.get("caption") or ""],
                    "ad_delivery_start_time": _day(r.get("start_date") or r.get("startDate") or r.get("start_date_formatted")),
                    "ad_delivery_stop_time": None if r.get("is_active") else _day(r.get("end_date") or r.get("endDate") or r.get("end_date_formatted")),
                    "publisher_platforms": [str(p).lower() for p in (r.get("publisher_platform") or r.get("publisherPlatform") or [])],
                    "eu_total_reach": _find(r, ["eu_total_reach"]), "target_ages": [], "target_gender": _find(r, ["gender_audience", "target_gender"]) or "",
                    "age_country_gender_reach_breakdown": _find(r, ["age_country_gender_reach_breakdown"]) or [],
                    "display_format": fmt, "cta": snap.get("cta_text") or "", "collation_count": r.get("collation_count"),
                    "target_age_min": (_find(r, ["age_audience"]) or {}).get("min"), "target_age_max": (_find(r, ["age_audience"]) or {}).get("max"),
                    "target_countries": [x.get("name") for x in (_find(r, ["location_audience"]) or []) if isinstance(x, dict) and not x.get("excluded")]})
    return out


def normalise(paths, as_of=None):
    """One row per ad, plus one row per ad x country x age x gender of reach."""
    ads, demo = [], []
    for path in ([paths] if isinstance(paths, (str, Path)) else paths):
        recs = _records(path)
        if recs and ("snapshot" in recs[0] or "ad_archive_id" in recs[0]):
            recs = from_scraper(recs)
        for r in recs:
            start = pd.to_datetime(r.get("ad_delivery_start_time"), errors="coerce")
            stop = pd.to_datetime(r.get("ad_delivery_stop_time"), errors="coerce")
            ads.append(dict(ad_id=str(r.get("id")), page_id=str(r.get("page_id", "")), page_name=r.get("page_name", ""),
                            headline=_join(r.get("ad_creative_link_titles")), body=_join(r.get("ad_creative_bodies")),
                            description=_join(r.get("ad_creative_link_descriptions")), caption=_join(r.get("ad_creative_link_captions")),
                            start=start, stop=stop, platforms=",".join(sorted(r.get("publisher_platforms") or [])),
                            languages=",".join(r.get("languages") or []), eu_total_reach=pd.to_numeric(r.get("eu_total_reach"), errors="coerce"),
                            display_format=r.get("display_format", ""), cta=r.get("cta", ""), target_age_min=pd.to_numeric(r.get("target_age_min"), errors="coerce"),
                            target_age_max=pd.to_numeric(r.get("target_age_max"), errors="coerce"), target_countries=",".join(r.get("target_countries") or []),
                            collation_count=pd.to_numeric(r.get("collation_count"), errors="coerce"), target_gender=r.get("target_gender", ""), target_ages=_join([str(a) for a in (r.get("target_ages") or [])]),
                            source_file=Path(path).name))
            for c in r.get("age_country_gender_reach_breakdown") or []:
                for a in c.get("age_gender_breakdowns") or []:
                    for g in ("male", "female", "unknown"):
                        if a.get(g):
                            demo.append(dict(ad_id=str(r.get("id")), country=c.get("country"), age=a.get("age_range"), gender=g, reach=float(a[g])))
    ads = pd.DataFrame(ads).drop_duplicates("ad_id")
    if ads.empty:
        raise ValueError("No ads found in the supplied files.")
    as_of = pd.Timestamp(as_of) if as_of else max(ads["start"].max(), ads["stop"].max())
    ads["still_running"] = ads["stop"].isna()
    ads["days_running"] = ((ads["stop"].fillna(as_of) - ads["start"]).dt.days + 1).clip(lower=1)
    ads["text"] = (ads["headline"] + ". " + ads["body"] + ". " + ads["description"]).str.strip(". ")
    ads["text_key"] = ads["text"].str.lower().map(lambda t: re.sub(r"[^\w]+", " ", t).strip())
    ads["has_video_platform"] = ads["platforms"].str.contains("instagram").astype(int)
    demo = pd.DataFrame(demo, columns=["ad_id", "country", "age", "gender", "reach"])
    if len(demo):
        tot = demo.groupby("ad_id")["reach"].sum()
        shares = demo.assign(share=demo["reach"] / demo["ad_id"].map(tot))
        wide = shares.pivot_table(index="ad_id", columns="gender", values="share", aggfunc="sum").add_prefix("share_").reset_index()
        age = shares.pivot_table(index="ad_id", columns="age", values="share", aggfunc="sum").add_prefix("share_age_").reset_index()
        ads = ads.merge(wide, on="ad_id", how="left").merge(age, on="ad_id", how="left")
        top = demo.groupby(["ad_id", "country"])["reach"].sum().reset_index().sort_values("reach").groupby("ad_id").tail(1)
        ads = ads.merge(top[["ad_id", "country"]].rename(columns={"country": "main_country"}), on="ad_id", how="left")
    return ads, demo


def split(ads, train_share=0.4):
    """Time-ordered, text-grouped split. Returns ads with a `split` column and a summary."""
    ads = ads.copy()
    first = ads.groupby("text_key")["start"].min().sort_values()
    n_train = int(np.floor(len(first) * train_share))
    train_keys = set(first.index[:n_train])
    ads["split"] = np.where(ads["text_key"].isin(train_keys), "train", "test")
    boundary = first.iloc[n_train] if n_train < len(first) else pd.NaT
    summary = {"ads": int(len(ads)), "distinct_creatives": int(len(first)), "train_ads": int((ads.split == "train").sum()),
               "test_ads": int((ads.split == "test").sum()), "test_starts_on": str(boundary.date()) if pd.notna(boundary) else None,
               "pages": ads.groupby("page_name").size().to_dict(),
               "text_overlap_between_splits": int(len(set(ads[ads.split == "train"].text_key) & set(ads[ads.split == "test"].text_key))),
               "ads_without_text": int((ads["text_key"] == "").sum()), "ads_with_reach": int(ads["eu_total_reach"].notna().sum())}
    return ads, summary


def build(paths, out_dir, train_share=0.4, as_of=None):
    ads, demo = normalise(paths, as_of)
    ads, summary = split(ads, train_share)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ads.to_csv(out / "ads.csv", index=False)
    demo.to_csv(out / "reach_by_demographic.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return ads, demo, summary


if __name__ == "__main__":
    import sys
    _, _, s = build(sys.argv[2:], sys.argv[1])
    print(json.dumps(s, indent=2, ensure_ascii=False))
