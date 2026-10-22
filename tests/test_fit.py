import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from fit import fit_score

CFG = dict(topic="eczema|itch", form="balm|stick", audience="mum|baby", angles={"нощи": "night|sleep", "билки": "calendula|herb"})


def funnel(kind, text):
    return dict(steps=[dict(type=kind, headline=text, sections=[])], angle="", tech="")


class Fit(unittest.TestCase):
    def test_advertorial_on_topic_beats_offtopic_pdp(self):
        good, _, _ = fit_score(funnel("advertorial", "eczema balm for baby, mum story, itch at night, calendula herb"), CFG, dict(reviews=100, media=10))
        bad, _, _ = fit_score(funnel("PDP", "collagen for dogs"), CFG, dict(reviews=100, media=10))
        self.assertGreater(good, bad + 30)

    def test_medical_claims_lower_safety(self):
        _, clean, _ = fit_score(funnel("LP", "eczema balm"), CFG, None)
        _, risky, _ = fit_score(funnel("LP", "eczema balm cures eczema, steroid free, heals, clinically proven, 97% success " * 3), CFG, None)
        self.assertLess(risky["safety"], clean["safety"])

    def test_few_photos_lower_proof(self):
        text = "eczema balm " + " ".join(f"„Great product for my baby number {i} truly“" for i in range(10))
        _, many, _ = fit_score(funnel("LP", text), CFG, dict(reviews=300, media=12))
        _, few, _ = fit_score(funnel("LP", text), CFG, dict(reviews=300, media=1))
        self.assertGreater(many["proof"], few["proof"])


if __name__ == "__main__":
    unittest.main()
