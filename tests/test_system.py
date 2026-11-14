"""Integration checks for leakage boundaries, cold starts and decision invariants."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from audiences import fingerprint
from contracts import check_predictions
from decide import creative_plan, daily_budget_plan
from features import RAW, _cpm_prior, build, history_rows, load_history, load_test
from model import Forecaster, finite_quantile
from simulation import simulate


class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_history()
        cls.train = cls.history[cls.history.data < "2026-11-02"]
        cls.val = cls.history[cls.history.data >= "2026-11-02"]
        cls.model = Forecaster().fit(cls.train).calibrate(cls.val)
        cls.future = load_test()
        cls.pred = cls.model.predict(cls.future)
        cls.output = pd.concat([cls.future[["data", "vertical", "campaign_id", "adset_id", "ad_id", "asset_id",
                                          "leva", "formato", "budget_giornaliero_adset"]], cls.pred], axis=1)

    def test_all_required_keys_and_cold_ads_have_predictions(self):
        report = check_predictions(pd.read_csv(RAW / "da_prevedere.csv"), self.output)
        self.assertEqual(report["predicted_rows"], 699)
        unknown = ~self.future.ad_id.isin(self.model.seen_ads)
        self.assertTrue(unknown.any())
        self.assertTrue(self.pred.loc[unknown, "cold_start"].eq(1).all())
        self.assertTrue(np.isfinite(self.pred.loc[unknown, "ctr_pred"]).all())

    def test_missing_duplicate_and_changed_metadata_are_rejected(self):
        required = pd.read_csv(RAW / "da_prevedere.csv")
        for bad in [self.output.iloc[:-1], pd.concat([self.output.iloc[:-1], self.output.iloc[[0]]])]:
            with self.assertRaises(ValueError):
                check_predictions(required, bad)
        bad = self.output.copy()
        bad["asset_id"] = bad.asset_id.astype(str)
        bad.loc[0, "asset_id"] = "WRONG"
        with self.assertRaisesRegex(ValueError, "metadata mismatch"):
            check_predictions(required, bad)

    def test_calibration_cannot_overlap_training(self):
        with self.assertRaisesRegex(ValueError, "strictly after training"):
            self.model.calibrate(self.train.tail(10))

    def test_partial_month_market_observation_is_not_available_to_earlier_forecast(self):
        observed = _cpm_prior()
        projected = _cpm_prior("2026-10-18")
        self.assertAlmostEqual(projected["2026-10"], observed["2026-09"] * observed["2025-10"] / observed["2025-09"])
        self.assertEqual(_cpm_prior("2026-11-01")["2026-10"], observed["2026-10"])

    def test_finite_sample_calibration_uses_order_statistic(self):
        self.assertEqual(finite_quantile([1,2,3,4]), 4)

    def test_quality_exclusions_are_traceable(self):
        raw = history_rows()
        self.assertEqual(len(raw), 1879)
        self.assertEqual(len(raw) - len(self.history), raw.quality_reason.ne("").sum())
        self.assertEqual(raw.quality_reason.ne("").sum(), 10)

    def test_audience_inference_does_not_depend_on_numeric_id_suffix(self):
        original = fingerprint(self.history)
        renamed = self.history.copy()
        mapping = {key: f"audience-letter-{chr(65+i)}" for i,key in enumerate(original.index)}
        renamed["adset_id"] = renamed.adset_id.astype(str).map(mapping)
        changed = fingerprint(renamed)
        self.assertEqual({mapping[key]: value for key,value in original.profile.items()}, changed.profile.to_dict())

    def test_daily_optimization_preserves_budget_and_bounds(self):
        plan = daily_budget_plan(self.output)
        self.assertTrue(plan.solver_success.all())
        group = plan.groupby(["data", "campaign_id"])
        np.testing.assert_allclose(group.budget.sum(), group.budget_proposed.sum(), atol=1e-5)
        self.assertTrue(((plan.budget_proposed / plan.budget).between(.8-1e-7,1.2+1e-7)).all())
        np.testing.assert_allclose(plan.budget_proposed*100, np.round(plan.budget_proposed*100), atol=1e-6)
        self.assertTrue((plan.campaign_gain_clicks_per_day > -1e-5).all())

    def test_creatives_are_compared_on_common_dates(self):
        recommendations = creative_plan(self.output)
        for rec in recommendations.to_dict("records"):
            sample = self.output[self.output.adset_id == rec["adset_id"]]
            sample = sample[sample.data.between(rec["comparison_start"], rec["comparison_end"])]
            sizes = sample.groupby("ad_id", observed=True).data.nunique()
            self.assertTrue(sizes.eq(rec["comparison_days"]).all())

    def test_synthetic_panel_conserves_ctr_under_extreme_assumptions(self):
        for ctr in [.2,1.2,4.0]:
            panel, metrics = simulate(ctr,"beauty_skincare",{"hook_first2s":1,"timer":1},strength=2,age_weights=[0,1,99])
            self.assertAlmostEqual(metrics["calibrated_ctr_%"],ctr,places=10)
            self.assertEqual(panel.simulated_viewers.sum(),10000)
            self.assertTrue((panel.simulated_clicks <= panel.simulated_viewers).all())
        with self.assertRaises(ValueError):
            simulate(1,"beauty_skincare",{},age_weights=[0,0,0])

    def test_new_creative_recovers_without_a_saved_model(self):
        import score_new
        score_new._cached_model.cache_clear()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(score_new, "OUT", Path(folder)), patch.object(score_new, "fit_production", return_value=self.model) as fit:
                result = score_new.score("beauty_skincare", "scarcity", "video", 15, "Routine semplice", "Prodotti per ogni giorno", "Acquista ora",
                                        "Creator parla in camera nei primi 2 secondi.")
                self.assertEqual(len(result[0]),4)
                self.assertTrue(np.isfinite(result[0].ctr).all())
                self.assertTrue((Path(folder)/"model.pkl").exists())
                fit.assert_called_once()
        score_new._cached_model.cache_clear()

    def test_invalid_launch_and_missing_copy_are_actionable(self):
        import score_new
        with self.assertRaisesRegex(ValueError,"headline"):
            score_new.score("beauty_skincare","scarcity","video",15,"","text","Acquista ora","description")
        with self.assertRaisesRegex(ValueError,"Launch date"):
            score_new._frame("beauty_skincare",{},launch="2026-12-01")


if __name__ == "__main__":
    unittest.main()
