"""The generic engine must run from a config alone, on full and on minimal inputs."""
import unittest
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from adsim import Engine, load                      # noqa: E402
from adsim.simulate import audiences, simulate, what_if_budget   # noqa: E402


class FullConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load(ROOT / "configs" / "wevion_bighack.json")
        cls.b["cfg"]["encoder"] = "tfidf"            # tests must not need a model download
        cls.e = Engine(cls.b["cfg"]).calibrate(cls.b["history"], cls.b["creatives"]).fit(cls.b["history"], cls.b["creatives"])

    def test_anomalies_found_by_rule(self):
        flagged = self.b["history"].query("quality != ''")
        self.assertEqual(set(flagged["date"].dt.strftime("%Y-%m-%d")), {"2026-10-14", "2026-10-21", "2026-11-09"})

    def test_forecast_covers_every_future_row(self):
        p = self.e.predict(self.b["future"])
        self.assertEqual(len(p), len(self.b["future"]))
        self.assertTrue(np.isfinite(p[["ctr", "cpm"]].values).all())
        self.assertTrue(((p.ctr_lo < p.ctr) & (p.ctr < p.ctr_hi) & (p.cpm_lo < p.cpm) & (p.cpm < p.cpm_hi)).all())

    def test_budget_response_is_structural(self):
        aud = self.b["future"]["audience_id"].iloc[0]
        t = what_if_budget(self.e, self.b["future"][self.b["future"]["audience_id"] == aud])
        self.assertTrue(t["cpm"].is_monotonic_increasing)        # more budget, higher price
        self.assertTrue(t["clicks"].is_monotonic_increasing)     # more budget, more clicks
        self.assertTrue(t["marginal_clicks_per_euro"].dropna().is_monotonic_decreasing)   # diminishing returns

    def test_simulation_and_audiences(self):
        s = simulate(self.e, self.b["future"].head(60), draws=200)
        self.assertTrue((s.clicks_p10 <= s.clicks_p90).all())
        probs = s.assign(d=self.b["future"].head(60)["date"].values).groupby(["d", "audience_id"]).p_best_in_audience.sum()
        self.assertTrue(np.allclose(probs, 1.0, atol=1e-6))
        self.assertEqual(len(audiences(self.e)), self.b["history"]["audience_id"].nunique())

    def test_unseen_creative_can_be_scored(self):
        new = self.b["creatives"].head(1).assign(creative_id="NEW-X")
        self.e.add_creatives(new)
        rows = self.b["future"].head(5).assign(creative_id="NEW-X", ad_id="NEW-AD")
        p = self.e.predict(rows)
        self.assertTrue(p["new_ad"].all() and np.isfinite(p["ctr"]).all())


class MinimalConfig(unittest.TestCase):
    def test_history_only_customer(self):
        b = load(ROOT / "configs" / "minimal_example.json")
        self.assertIn("season index", b["missing_optional_inputs"])
        cut = pd.Timestamp("2026-11-02")
        e = Engine(b["cfg"]).fit(b["history"][b["history"]["date"] < cut], b["creatives"])
        val = b["history"][(b["history"]["date"] >= cut) & (b["history"]["quality"] == "")]
        p = e.predict(val)
        self.assertLess(np.mean(np.abs(np.log(val["cpm"].values / p["cpm"].values))), 0.15)


if __name__ == "__main__":
    unittest.main()
