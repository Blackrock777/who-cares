import tempfile
import unittest
import warnings

import numpy as np

from adsim import Engine, load
from adsim.population import AudienceModel, audience_effects, load_priors
from adsim.world import make_company

warnings.filterwarnings("ignore")


class PriorsTest(unittest.TestCase):
    def test_vertical_mixes_are_distributions_with_sources(self):
        p = load_priors()
        self.assertEqual(len(p["cells"]), 10)
        for v, m in p["verticals"].items():
            self.assertAlmostEqual(sum(m["mean"].values()), 1.0, places=3, msg=v)
            self.assertGreater(m["kappa"], 0)
            self.assertIn("source_brand", m)

    def test_cpm_gender_ratio_agrees_with_independent_benchmark(self):
        c = load_priors()["cross_checks"]["cpm_female_over_male"]
        self.assertLess(abs(c["kaggle_adjusted"] - c["lebesgue_2025"]), 0.1)


class InferenceTest(unittest.TestCase):
    def setUp(self):
        self.m = AudienceModel(draws=8000)

    def test_no_signal_returns_the_prior(self):
        s = self.m.infer("abbigliamento", 0.0, 0.0, y_freq=0.0).summary()
        self.assertLess(abs(s["share_female"]["mean"] - s["share_female"]["prior"]), 0.03)
        self.assertLess(abs(s["mean_age"]["mean"] - s["mean_age"]["prior"]), 1.5)
        self.assertEqual(s["label"]["confidence"], "mostly the vertical prior")

    def test_high_frequency_and_price_reads_as_warm_not_as_older_women(self):
        s = self.m.infer("beauty_skincare", 0.7, 0.45, y_freq=0.18).summary()
        self.assertGreater(s["p_warm"], 0.9)
        self.assertLess(abs(s["mean_age"]["mean"] - s["mean_age"]["prior"]), 2.0)

    def test_cheaper_and_lower_ctr_moves_younger(self):
        s = self.m.infer("pet_ecommerce", -0.25, -0.25, y_freq=0.0).summary()
        self.assertLess(s["mean_age"]["mean"], s["mean_age"]["prior"])

    def test_unknown_vertical_falls_back_to_population(self):
        s = self.m.infer("furniture", 0.0, 0.0).summary()
        self.assertTrue(0.4 < s["share_female"]["mean"] < 0.6)


class WorldTest(unittest.TestCase):
    def test_company_loads_through_config_and_engine_fits(self):
        with tempfile.TemporaryDirectory() as d:
            cfg, truth = make_company(5, d, end="2026-10-15")
            b = load(cfg)
            self.assertGreater(len(b["history"]), 50)
            e = Engine(b["cfg"]).fit(b["history"], b["creatives"])
            self.assertTrue(np.isfinite(e.k["cpm"]))
            eff = audience_effects(b["history"])
            self.assertEqual(set(eff["audience_id"]), set(truth["audiences_truth"]))


if __name__ == "__main__":
    unittest.main()
