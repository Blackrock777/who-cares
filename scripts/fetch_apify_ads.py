"""Pull Ad Library ads through an Apify actor and build the dataset.

Needs .env.apify at the project root:   APIFY_TOKEN=...
Actor: curious_coder/facebook-ads-library-scraper (pay per result; about $0.75 per 1,000 ads when
this was written, check the actor page). This is a third-party scraper of Meta's public Ad
Library, run under your Apify account; you are responsible for that use.

  python scripts/fetch_apify_ads.py --limit 30                 small paid test, prints the fields returned
  python scripts/fetch_apify_ads.py --limit 1500               full pull (limit is per source URL)
  python scripts/fetch_apify_ads.py --sources URL [URL ...]    override the default Sephora sources
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTOR = "curious_coder~facebook-ads-library-scraper"


def library_url(query, country):
    q = urllib.parse.urlencode({"active_status": "all", "ad_type": "all", "country": country, "q": query,
                                "search_type": "keyword_unordered", "media_type": "all"})
    return "https://www.facebook.com/ads/library/?" + q


def page_url(page_id, country="ALL"):
    return ("https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=%s&is_targeted_country=false"
            "&media_type=all&search_type=page&view_all_page_id=%s" % (country, page_id))


DEFAULT_SOURCES = [library_url("Sephora", "IT"), library_url("Sephora", "FR")]


def token():
    f = ROOT / ".env.apify"
    if not f.exists():
        sys.exit("Missing .env.apify. Create it with one line:  APIFY_TOKEN=<your token>")
    for line in f.read_text().splitlines():
        if line.strip().startswith("APIFY_TOKEN="):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit(".env.apify has no APIFY_TOKEN= line.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, required=True, help="max ads per source URL (this is what you pay for)")
    ap.add_argument("--sources", nargs="+", default=DEFAULT_SOURCES)
    ap.add_argument("--page-ids", nargs="+", help="advertiser page ids: pulls each page's own ads instead of a keyword search")
    ap.add_argument("--name", default="sephora")
    ap.add_argument("--train-share", type=float, default=0.4)
    ap.add_argument("--page-filter", default="sephora", help="keep only advertisers whose page name contains this (case-insensitive); '' keeps all")
    a = ap.parse_args()
    tok = token()
    if a.page_ids:
        a.sources = [page_url(p) for p in a.page_ids]
    body = {"urls": [{"url": u} for u in a.sources], "scrapeAdDetails": True, "limitPerSource": a.limit,
            "scrapePageAds.activeStatus": "all", "scrapePageAds.countryCode": "ALL"}
    print(f"running {ACTOR} on {len(a.sources)} sources, up to {a.limit} ads each (about ${0.75 * a.limit * len(a.sources) / 1000:.2f}; the actor may overshoot each source by ~30 ads) ...", flush=True)

    def call(url, data=None):
        req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit(f"Apify error {e.code}: {e.read().decode(errors='replace').replace(tok, '<token>')[:500]}")
    import time
    run = call(f"https://api.apify.com/v2/acts/{ACTOR}/runs?" + urllib.parse.urlencode({"token": tok}), body)["data"]
    while run["status"] in ("READY", "RUNNING"):
        time.sleep(15)
        run = call(f"https://api.apify.com/v2/actor-runs/{run['id']}?" + urllib.parse.urlencode({"token": tok}))["data"]
        print("  status", run["status"], flush=True)
    if run["status"] != "SUCCEEDED":
        sys.exit(f"Apify run ended with status {run['status']}")
    items, offset = [], 0
    while True:
        page = call(f"https://api.apify.com/v2/datasets/{run['defaultDatasetId']}/items?" + urllib.parse.urlencode({"token": tok, "format": "json", "clean": "true", "offset": offset, "limit": 500}))
        items += page
        offset += len(page)
        if len(page) < 500:
            break
    out = ROOT / "data" / "external" / "ad_library" / a.name
    out.mkdir(parents=True, exist_ok=True)
    kept = [i for i in items if a.page_filter.lower() in str(i.get("page_name") or (i.get("snapshot") or {}).get("page_name") or "").lower()]
    (out / "raw.json").write_text(json.dumps(kept, ensure_ascii=False))
    print(f"received {len(items)} items, kept {len(kept)} from pages matching '{a.page_filter}' -> {out / 'raw.json'}")
    if not kept:
        sys.exit("Nothing to build. Top-level fields of the first item: " + (", ".join(sorted(items[0].keys())) if items else "none"))
    print("top-level fields:", ", ".join(sorted(kept[0].keys())))
    sys.path.insert(0, str(ROOT))
    from adsim.adlibrary import build
    _, _, summary = build([out / "raw.json"], out, train_share=a.train_share)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
