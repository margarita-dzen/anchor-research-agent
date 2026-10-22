"""Тестове за събирането на данни (agent/adlib): обединяване, крайни URL-и, EU обхват, сравнение на снимки."""
import datetime, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "agent"))
sys.path.insert(0, os.path.join(HERE, "..", "agent", "adlib"))
import consolidate, eu_reach, harvest, resolve_urls, runconfig, scrape, snapshot_diff  # noqa: E402
from evidence import aggregate  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "adlib")
TODAY = datetime.date(2026, 10, 20)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def load_fixture_ads():
    cfg = runconfig.load(os.path.join(FIX, "run.json"))
    files = consolidate.raw_files(os.path.join(FIX, "raw"))
    return cfg, {a["collation_id"]: a for a in consolidate.consolidate([consolidate.read_raw(f) for f in files], cfg, TODAY)}


class RunConfig(unittest.TestCase):
    def test_defaults_and_parallel_cap(self):
        cfg = runconfig.load(os.path.join(FIX, "run.json"))
        self.assertEqual(cfg["scrape"]["parallel"], 2)
        self.assertTrue(cfg["_dir"].endswith(os.path.join("adlib", "out")))
        self.assertEqual(runconfig.scrape_date(cfg), TODAY)
        self.assertEqual(runconfig.raw_name("acne", "DE", "Akne Creme"), "acne__DE__Akne_Creme.json")

    def test_example_config_loads(self):
        cfg = runconfig.load(os.path.join(HERE, "..", "runs", "example", "run.json"))
        self.assertEqual(set(cfg["flags"]), {"mom", "herbal"})
        self.assertGreater(len(cfg["queries"]), 50)

    def test_bad_rule_rejected(self):
        with self.assertRaises(ValueError):
            runconfig.validate(dict(queries=[], categories={}, flags={}, products=[{"product": "x", "require": ["nope"]}]))

    def test_harvest_jobs_and_top_pages(self):
        cfg = runconfig.load(os.path.join(FIX, "run.json"))
        jobs = harvest.keyword_jobs(cfg, limit=1, scrolls=1)
        self.assertEqual(len(jobs), 1)
        self.assertTrue(jobs[0]["out"].endswith("raw/acne__DE__Akne_Creme.json"))
        ads = [dict(page_id="1", brand="A", active=True, duplicates=5, product="acne"),
               dict(page_id="2", brand="B", active=True, duplicates=1, product="acne"),
               dict(page_id="3", brand="C", active=True, duplicates=50, product="atopi")]
        self.assertEqual([p for p, _, _ in harvest.top_pages(ads, 5, {"acne"})], ["1", "2"])
        self.assertIn("view_all_page_id=1", scrape.library_url(page_id="1"))


class Consolidate(unittest.TestCase):
    def test_extract_ads_from_html(self):
        html = 'x{"ad_archive_id":"9","snapshot":{"body":{"text":"a } \\" {"}}}y {"ad_archive_id":"9"}'
        ads = scrape.extract_ads([html])
        self.assertEqual(len(ads), 1)

    def test_merge_exclude_and_products(self):
        _, ads = load_fixture_ads()
        self.assertEqual(sorted(ads), ["c1", "c3", "c4", "c7"])  # temu отпада
        c1 = ads["c1"]
        self.assertEqual(c1["countries"], ["DE", "GB"])
        self.assertEqual(c1["cats"], ["acne", "atopi"])
        self.assertEqual(c1["duplicates"], 9)
        self.assertTrue(c1["active"])
        self.assertEqual(c1["days_running"], 122)  # по-дългият вариант печели
        self.assertEqual(c1["brand"], "Clear Co")
        self.assertNotIn("�", c1["primary_text"])
        self.assertEqual(c1["product"], "acne")
        self.assertTrue(c1["mom"])
        self.assertEqual(c1["flags"], ["mom"])

    def test_atopi_rule_and_flags(self):
        _, ads = load_fixture_ads()
        self.assertEqual(ads["c3"]["product"], "atopi")
        self.assertEqual(ads["c3"]["flags"], ["mom", "herbal"])

    def test_dpa_and_legacy_raw(self):
        _, ads = load_fixture_ads()
        self.assertEqual(ads["c4"]["primary_text"], "Akne Serum mit Teebaum")
        self.assertEqual(ads["c4"]["format"], "carousel")
        self.assertEqual(ads["c7"]["product"], "acne")  # herbal заявка, тема акне
        self.assertEqual(ads["c7"]["queries"], ["herbal_ointment"])

    def test_output_fields_for_evidence(self):
        _, ads = load_fixture_ads()
        need = {"meta_ad_id", "collation_id", "brand", "page_id", "first_seen", "days_running", "active", "format",
                "headline", "primary_text", "landing_url", "landing_url_clean", "domain", "duplicates", "thumb",
                "video", "cta", "countries", "queries", "cats", "product", "flags"}
        for a in ads.values():
            self.assertFalse(need - set(a))
        passed, rejected = aggregate(list(ads.values()), TODAY, blocklist={})
        self.assertEqual(len(passed) + len(rejected), 4)


class EuReach(unittest.TestCase):
    def test_parse_eu(self):
        r = eu_reach.parse_details(read(os.path.join(FIX, "ad_details_eu.txt")))
        self.assertEqual(r["eu_reach"], 1124737)
        self.assertEqual(r["countries"], ["DE", "AT"])
        self.assertEqual(r["reach_by_country"]["DE"], 31563 + 116318 + 723 + 4 + 54)
        self.assertEqual(r["age"], [18, 65])

    def test_parse_non_eu_and_garbage(self):
        r = eu_reach.parse_details(read(os.path.join(FIX, "ad_details_us.txt")))
        self.assertIsNone(r["eu_reach"])
        self.assertFalse(r["targets_eu"])
        self.assertIsNone(eu_reach.parse_details('for (;;);{"error":1357004}'))

    def test_candidates_skip_cached_and_inactive(self):
        ads = [dict(meta_ad_id="1", active=True, days_running=10, duplicates=1),
               dict(meta_ad_id="2", active=False, days_running=999, duplicates=9),
               dict(meta_ad_id="3", active=True, days_running=500, duplicates=1)]
        self.assertEqual([a["meta_ad_id"] for a in eu_reach.candidates(ads, 5, cached={"3"})], ["1"])


class FakeWeb:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, method, timeout):
        self.calls.append((method, url))
        r = self.routes.get((method, url)) or self.routes.get(url)
        if r is None:
            raise OSError("няма връзка")
        if isinstance(r, Exception):
            raise r
        return r


class Resolve(unittest.TestCase):
    def test_clean_url(self):
        self.assertEqual(resolve_urls.clean_url("http://www.Shop.com/pages/a/?utm_source=x&variant=1&fbclid=y#top"),
                         "https://shop.com/pages/a?variant=1")
        self.assertEqual(resolve_urls.clean_url("https://a.com/?ad_id={{ad.id}}"), "https://a.com/")

    def test_redirect_and_head_fallback(self):
        web = FakeWeb({("HEAD", "https://bit.ly/x"): (405, "https://bit.ly/x", b""),
                       ("GET", "https://bit.ly/x"): (200, "https://shop.com/pages/lp/?utm_campaign=1", b"<html>")})
        r = resolve_urls.resolve("https://bit.ly/x", web)
        self.assertEqual(r["clean"], "https://shop.com/pages/lp")
        self.assertEqual(r["method"], "GET")

    def test_facebook_wrapper_and_meta_refresh(self):
        web = FakeWeb({"https://go.com/a": (200, "https://go.com/a", b'<meta http-equiv="refresh" content="0; url=/b">'),
                       "https://go.com/b": (200, "https://go.com/b", b"")})
        web.routes[("HEAD", "https://go.com/a")] = (403, "https://go.com/a", b"")
        r = resolve_urls.resolve("https://l.facebook.com/l.php?u=https%3A%2F%2Fgo.com%2Fa&h=AT0", web)
        self.assertEqual(r["clean"], "https://go.com/b")

    def test_unreachable_keeps_clean_original(self):
        r = resolve_urls.resolve("https://dead.com/lp?fbclid=1", FakeWeb({}))
        self.assertTrue(r["error"])
        self.assertEqual(r["clean"], "https://dead.com/lp")

    def test_cache_and_evidence_merge(self):
        web = FakeWeb({"https://bit.ly/x": (200, "https://s.com/pages/lp?utm_source=fb", b""),
                       "https://s.com/pages/lp?fbclid=9": (200, "https://s.com/pages/lp?fbclid=9", b"")})
        cache = {"https://old.com/x": dict(clean="https://old.com/x", checked=str(TODAY))}
        mapping, fetched = resolve_urls.resolve_all(["https://bit.ly/x", "https://s.com/pages/lp?fbclid=9",
                                                     "https://old.com/x"], cache, web, workers=2, today=TODAY)
        self.assertEqual(fetched, 2)  # old.com е от кеша
        self.assertEqual(len(set(mapping.values())), 2)
        ads = [dict(landing_url=u, landing_url_clean=u, active=True, duplicates=1, days_running=5,
                    first_seen="2026-10-01", countries=["DE"], product="acne", meta_ad_id=u)
               for u in ("https://bit.ly/x", "https://s.com/pages/lp?fbclid=9", "https://s.com/pages/lp/")]
        passed, _ = aggregate(ads, TODAY, blocklist={}, resolved=mapping)
        self.assertEqual([(p["url"], p["ads"]) for p in passed], [("https://s.com/pages/lp", 3)])
        no_map, rej = aggregate(ads, TODAY, blocklist={})
        self.assertEqual(no_map, [])  # без картата са 2 отделни URL-а под прага


class SnapshotDiff(unittest.TestCase):
    def test_diff(self):
        def a(cid, url, active=True, first="2026-09-01"):
            return dict(collation_id=cid, meta_ad_id="m" + cid, landing_url_clean=url, active=active,
                        first_seen=first, brand="B", product="acne")
        old = [a("1", "https://s.com/lp"), a("2", "https://s.com/lp"), a("3", "https://s.com/lp"),
               a("4", "https://o.com/lp"), a("9", "https://o.com/lp", active=False)]
        new = [a("1", "https://s.com/lp"), a("2", "https://s.com/lp", active=False),
               a("5", "https://s.com/lp", first="2026-10-25"), a("6", "https://s.com/lp", first="2026-10-01"),
               a("7", "https://www.s.com/lp/?utm_source=x", first="2026-10-30")]
        rows = {r["url"]: r for r in snapshot_diff.diff(old, new, TODAY)}
        s = rows["https://s.com/lp"]
        self.assertEqual((s["launched"], s["seen_late"], s["stopped"], s["missing"], s["running"]), (2, 1, 1, 1, 1))
        self.assertEqual(s["net"], 0)
        o = rows["https://o.com/lp"]
        self.assertEqual((o["missing"], o["net"]), (1, -1))  # неактивната 9 не се брои


if __name__ == "__main__":
    unittest.main()
