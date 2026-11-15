#!/bin/sh
# Downloads the public Kaggle dataset "Sales Conversion Optimization" (loveall/clicks-conversion-tracking)
# and writes the canonical file the adsim config expects. Check the dataset's licence on Kaggle before reuse.
set -e
D="$(cd "$(dirname "$0")/.." && pwd)/data/external/kaggle_sales_conversion"
mkdir -p "$D" && cd "$D"
curl -s -L -o kag.zip "https://www.kaggle.com/api/v1/datasets/download/loveall/clicks-conversion-tracking"
unzip -o -q kag.zip && rm kag.zip
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open("KAG_conversion_data.csv")))
for r in rows:
    r["date"] = "2017-08-01"; r["audience"] = r["age"] + "|" + r["gender"]; r["creative"] = "interest_" + r["interest"]
w = csv.DictWriter(open("canonical.csv", "w", newline=""), fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
PY
echo "wrote $D/canonical.csv"
