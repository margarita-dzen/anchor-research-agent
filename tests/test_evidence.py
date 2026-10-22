import datetime, os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from evidence import aggregate, evidence_score, norm_url

TODAY = datetime.date(2026, 10, 20)


def ad(url, active=True, dups=1, days=30, first="2026-09-01", cc=("US",), product="acne", brand="B"):
    return dict(landing_url_clean=url, active=active, duplicates=dups, days_running=days, first_seen=first,
                countries=list(cc), product=product, brand=brand, meta_ad_id=url + str(days))


class Evidence(unittest.TestCase):
    def test_norm_url(self):
        self.assertEqual(norm_url("http://www.Shop.com/pages/a/"), ("https://shop.com/pages/a", "shop.com"))

    def test_gate_rejects_noise(self):
        ads = [ad("http://instagram.com/x", days=1498, dups=9),
               ad("https://shop.com/", dups=9),
               ad("https://old.com/pages/lp", days=1200),
               ad("https://dead.com/pages/lp", active=False, dups=9),
               ad("https://l.instagram.com/pages/x", dups=9)]
        passed, rejected = aggregate(ads, TODAY, blocklist={"social": ["instagram.com"]})
        self.assertEqual(passed, [])
        self.assertEqual(len(rejected), 5)

    def test_single_ad_with_many_duplicates_passes(self):
        passed, _ = aggregate([ad("https://a.com/pages/lp", dups=6)], TODAY, blocklist={})
        self.assertEqual(len(passed), 1)

    def test_missing_traffic_not_penalised(self):
        base = dict(active_ads=20, duplicates=40, new_ads_30d=5, max_days=200, countries=3)
        no_traffic, _ = evidence_score({**base, "domain_visits": None})
        zero_traffic, _ = evidence_score({**base, "domain_visits": 0})
        self.assertGreater(no_traffic, zero_traffic)

    def test_scaling_page_beats_old_single(self):
        scaling = [ad("https://s.com/pages/lp", dups=3, first="2026-10-10", cc=("US", "DE")) for _ in range(20)]
        old = [ad("https://o.com/pages/lp", days=900, dups=2) for _ in range(3)]
        passed, _ = aggregate(scaling + old, TODAY, blocklist={})
        self.assertEqual(passed[0]["domain"], "s.com")
        self.assertLessEqual(passed[0]["evidence"], 100)


if __name__ == "__main__":
    unittest.main()
