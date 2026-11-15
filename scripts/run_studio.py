"""Pre-generate the creative studio runs shown on the static page (one per brand x audience).

  python scripts/run_studio.py                 all 12 audiences, 6 candidates each (12 API calls)
  python scripts/run_studio.py --only NDL-AS1  one audience

Writes out/studio/runs.json. Each run records the model, tokens and request id, so a run can be traced.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adsim.studio import Studio, api_key   # noqa: E402

OUT = ROOT / "out" / "studio" / "runs.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--redo", action="store_true", help="regenerate audiences that already have a run")
    a = ap.parse_args()
    if not api_key():
        sys.exit("No language model configured. Create .env.anthropic (ANTHROPIC_API_KEY=...) or .env.openrouter (OPENROUTER_API_KEY=...).")
    briefs = json.loads((ROOT / "configs" / "studio" / "briefs.json").read_text())
    st = Studio()
    runs = json.loads(OUT.read_text()) if OUT.exists() else {}
    auds = a.only or [f"{b}-AS{i}" for b in ("NDL", "CDF", "FGR") for i in range(1, 5)]
    tok = 0
    for aud in auds:
        brand = aud.split("-")[0]
        if aud in runs and not a.redo and not a.only:
            continue
        try:
            r = st.run(brand, aud, briefs[brand], a.n)
        except Exception as exc:                     # one failed audience never stops the batch
            print(f"{aud}: FAILED {exc}", flush=True)
            continue
        runs[aud] = r
        tok += r["meta"]["input_tokens"] + r["meta"]["output_tokens"]
        top = r["candidates"][0]
        print(f"{aud}: {len(r['candidates'])} candidates in {r['meta']['seconds']}s; best {top['leva']}/{top['formato']} "
              f"CTR {top['target']['ctr'] if top['target'] else 'n/a'} vs existing best {r['evidence']['benchmark_ctr']:.3f}", flush=True)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(runs, ensure_ascii=False, indent=1, default=str))
    print(f"wrote {OUT} ({len(runs)} runs, {tok} tokens this session)")


if __name__ == "__main__":
    main()
