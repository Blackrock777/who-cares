"""Exercise supported controls through Streamlit's application runner."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def assert_no_crash(self, app):
        self.assertEqual([exc.message for exc in app.exception], [])

    def test_all_campaigns_segments_metrics_and_windows(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/"app.py"), default_timeout=60).run()
        self.assert_no_crash(app)
        advertiser = lambda: next(x for x in app.selectbox if x.label == "Advertiser")
        segment = lambda: next(x for x in app.selectbox if x.label == "Audience segment")
        for vertical in ["beauty_skincare", "pet_ecommerce", "abbigliamento"]:
            advertiser().set_value(vertical).run()
            self.assert_no_crash(app)
            for adset in segment().options:
                segment().set_value(adset).run()
                self.assert_no_crash(app)
        for metric in ["cpm", "cpc", "ctr"]:
            app.radio[0].set_value(metric).run()
            self.assert_no_crash(app)
        window = next(x for x in app.selectbox if x.label == "Decision window")
        window.set_value("Pre Black Week (16-22 Nov)").run()
        self.assert_no_crash(app)

    def test_creative_prediction_and_invalid_viewer_scenario(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/"app.py"), default_timeout=60).run()
        app.button[0].click().run()
        self.assert_no_crash(app)
        self.assertTrue(len(app.slider))
        app.slider[0].set_value(1.5).run()
        self.assert_no_crash(app)
        for number in app.number_input:
            if "age weight" in number.label:
                number.set_value(0)
        app.run()
        self.assert_no_crash(app)
        self.assertTrue(any("positive total" in err.value for err in app.error))


if __name__ == "__main__":
    unittest.main()
