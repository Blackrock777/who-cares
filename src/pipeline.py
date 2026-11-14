"""Regenerate all deliverables from the unchanged organisers' kit."""
import argparse
import shutil
from pathlib import Path

import audiences
import decide
import model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-rolling", action="store_true", help="Skip the earlier-window stability check")
    args = parser.parse_args()
    out = Path(__file__).resolve().parents[1] / "out"
    out.mkdir(exist_ok=True)
    # Preserve the initially supplied outputs on the first regeneration.
    archive = out / "audit"
    archive.mkdir(exist_ok=True)
    for filename in ["predictions.csv", "validation.csv", "audiences.json", "decisions.json"]:
        source, target = out / filename, archive / f"original_{filename}"
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
    if not args.skip_rolling:
        model.rolling_validate()
    model.validate()
    model.predict()
    audiences.main()
    decide.main()
    print("Complete: checked predictions, audience evidence, decisions, validation and run manifest in out/.")


if __name__ == "__main__":
    main()
