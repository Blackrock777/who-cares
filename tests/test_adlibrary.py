"""Schema and split checks on a hand-written fixture in the Ad Library API format.
The fixture is not real advertiser data."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adsim.adlibrary import build     # noqa: E402


def fixture():
    ads = []
    for i in range(20):
        ads.append({"id": str(1000 + i), "page_id": "1", "page_name": "Fixture Brand",
                    "ad_creative_bodies": [f"Texte publicitaire numero {i // 2}"], "ad_creative_link_titles": ["Titre"],
                    "ad_delivery_start_time": f"2026-0{1 + i // 4}-0{1 + i % 4}",
                    "ad_delivery_stop_time": None if i % 5 == 0 else f"2026-0{2 + i // 4}-15",
                    "publisher_platforms": ["facebook", "instagram"], "eu_total_reach": 1000 * (i + 1),
                    "age_country_gender_reach_breakdown": [{"country": "FR", "age_gender_breakdowns": [
                        {"age_range": "18-24", "female": 300.0, "male": 100.0}, {"age_range": "25-34", "female": 400.0, "male": 200.0}]}]})
    return ads


class AdLibrary(unittest.TestCase):
    def test_build_and_split(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "ads.json"
            src.write_text(json.dumps(fixture()))
            ads, demo, s = build([src], Path(d) / "out", train_share=0.4, as_of="2026-07-01")
        self.assertEqual(s["ads"], 20)
        self.assertEqual(s["text_overlap_between_splits"], 0)          # same copy never on both sides
        self.assertGreater(s["test_ads"], s["train_ads"])              # the larger share is held out
        self.assertLessEqual(ads[ads.split == "train"].start.max(), ads[ads.split == "test"].start.max())
        self.assertAlmostEqual(ads["share_female"].iloc[0], 0.7)
        self.assertEqual(len(demo), 20 * 4)
        self.assertTrue((ads.days_running >= 1).all())


if __name__ == "__main__":
    unittest.main()
