"""Fetch ads from Meta's official Ad Library API and build the dataset.

Needs a token in .env.meta at the project root:   META_AD_LIBRARY_TOKEN=...
The token must come from a Meta developer account whose owner has confirmed identity
(facebook.com/ID); Meta requires that for Ad Library API access.

Usage:
  python scripts/fetch_ad_library.py pages   --term Sephora --countries IT FR
        lists the advertiser pages that match, with their page ids and ad counts (cheap)
  python scripts/fetch_ad_library.py ads     --page-ids 123 456 --countries IT FR
        downloads every ad of those pages delivered to those countries, then builds
        data/external/ad_library/<name>/{ads.csv, reach_by_demographic.csv, summary.json}
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://graph.facebook.com/v21.0/ads_archive"
FIELDS = ("id,page_id,page_name,ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions,"
          "ad_creative_link_captions,ad_delivery_start_time,ad_delivery_stop_time,publisher_platforms,languages,"
          "eu_total_reach,target_ages,target_gender,target_locations,age_country_gender_reach_breakdown,ad_snapshot_url")


def token():
    f = ROOT / ".env.meta"
    if not f.exists():
        sys.exit("Missing .env.meta. Create it with one line:  META_AD_LIBRARY_TOKEN=<your token>")
    for line in f.read_text().splitlines():
        if line.strip().startswith("META_AD_LIBRARY_TOKEN="):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit(".env.meta has no META_AD_LIBRARY_TOKEN= line.")


def pull(params, limit_pages=200):
    url = API + "?" + urllib.parse.urlencode(params)
    out = []
    for _ in range(limit_pages):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                page = json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            body = body.replace(params["access_token"], "<token>")
            sys.exit(f"Ad Library API error {e.code}: {body[:400]}")
        out += page.get("data", [])
        url = page.get("paging", {}).get("next")
        if not url:
            break
        time.sleep(1.0)                     # stay well inside the rate limit
    return out


def base(a):
    return {"access_token": token(), "ad_reached_countries": json.dumps(a.countries), "ad_active_status": "ALL",
            "ad_type": "ALL", "limit": 200}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["pages", "ads"])
    ap.add_argument("--term", default="Sephora")
    ap.add_argument("--countries", nargs="+", default=["IT", "FR"])
    ap.add_argument("--page-ids", nargs="+")
    ap.add_argument("--name", default="sephora")
    ap.add_argument("--train-share", type=float, default=0.4)
    a = ap.parse_args()
    if a.command == "pages":
        rows = pull(dict(base(a), search_terms=a.term, fields="page_id,page_name"), limit_pages=15)
        for (pid, name), n in Counter((r["page_id"], r["page_name"]) for r in rows).most_common(40):
            print(f"{n:6d} ads  page_id {pid}  {name}")
        return
    if not a.page_ids:
        sys.exit("Give --page-ids (run the 'pages' command first to find them).")
    out = ROOT / "data" / "external" / "ad_library" / a.name
    out.mkdir(parents=True, exist_ok=True)
    rows = pull(dict(base(a), search_page_ids=json.dumps(a.page_ids), fields=FIELDS))
    raw = out / "raw.json"
    raw.write_text(json.dumps(rows, ensure_ascii=False))
    print(f"fetched {len(rows)} ads -> {raw}")
    sys.path.insert(0, str(ROOT))
    from adsim.adlibrary import build
    _, _, summary = build([raw], out, train_share=a.train_share)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
