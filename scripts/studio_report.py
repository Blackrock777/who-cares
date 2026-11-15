"""Summarise the pre-generated studio runs, including a check a reviewer would ask for:
does writing for a specific audience help, according to the forecaster?

For each audience A, compare the forecast CTR in A of candidates written for A with that of
candidates written for the brand's other audiences. If targeting worked, the first should be higher.

  python scripts/studio_report.py        writes out/studio/report.json
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
runs = json.loads((ROOT / "out" / "studio" / "runs.json").read_text())

rows = []
for aud, r in runs.items():
    for c in r["candidates"]:
        for s in c.get("by_audience") or []:
            rows.append({"written_for": aud, "scored_in": s["audience"], "ctr": s["ctr"], "brand": aud.split("-")[0]})

lifts = {}
for aud in runs:
    own = [x["ctr"] for x in rows if x["written_for"] == aud and x["scored_in"] == aud]
    other = [x["ctr"] for x in rows if x["written_for"] != aud and x["scored_in"] == aud and x["brand"] == aud.split("-")[0]]
    if own and other:
        lifts[aud] = round(float(np.mean(own) / np.mean(other) - 1), 3)

cands = [c for r in runs.values() for c in r["candidates"]]
scored = [c for c in cands if c.get("target")]
report = {
    "runs": len(runs), "candidates": len(cands), "rejected": sum(c["rejected"] for c in cands),
    "dropped_malformed": sum(r["meta"].get("dropped_invalid", 0) for r in runs.values()),
    "flagged_invented_numbers": sum(any(f["code"] == "claim" for f in c["flags"]) for c in cands),
    "beyond_training": sum(c.get("novelty") == "beyond" for c in cands),
    "clearly_better_than_best_existing": sum(bool(c.get("clearly_better")) for c in scored),
    "best_new_vs_best_existing": {a: max((c.get("vs_best_existing") or 0) for c in r["candidates"]) for a, r in runs.items()},
    "targeting_lift_in_own_audience": lifts,
    "targeting_lift_mean": round(float(np.mean(list(lifts.values()))), 3) if lifts else None,
    "models": sorted({r["meta"]["model"] for r in runs.values()}),
    "tokens": sum(r["meta"]["input_tokens"] + r["meta"]["output_tokens"] for r in runs.values()),
}
(ROOT / "out" / "studio" / "report.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
