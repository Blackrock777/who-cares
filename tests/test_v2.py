import unittest
import warnings

from adsim import Engine, load

warnings.filterwarnings("ignore")


class AudienceInteractionTest(unittest.TestCase):
    """Audience x lever effects are an option, off by default: on the kit they did not improve
    rolling-window accuracy and an F-test on raw data found no audience x lever effect (p > 0.7)."""

    @classmethod
    def setUpClass(cls):
        cls.b = load("configs/wevion_bighack.json")

    def test_off_by_default(self):
        self.assertEqual(Engine(self.b["cfg"]).audience_interactions, 0.0)

    def test_on_adds_a_block_and_still_fits(self):
        e = Engine(dict(self.b["cfg"], audience_interactions=True)).fit(self.b["history"], self.b["creatives"])
        self.assertTrue(any(name.startswith("ux_") for _, name, _ in e._blocks(False)))
        p = e.predict(self.b["future"].head(20))
        self.assertTrue((p["ctr"] > 0).all())


if __name__ == "__main__":
    unittest.main()
