import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "agent"))
sys.path.insert(0, os.path.join(ROOT, "agent", "qa"))
import review_stats
import claims
from check_media import norm_url, duplicates, rotated, cropped_thumb, analyze
from run_qa import ALLOWED_MISSING

BANK = [
    dict(product="acne", name="Ана", body="Кожата се изчисти за седмица.", rating=5),
    dict(product="acne", name="Бети", body="Видях разлика след 2 седмици.", rating=5),
    dict(product="acne", name="Вера", body="Още от първата вечер е по-спокойна, а след месец няма нищо.", rating=5),
    dict(product="acne", name="Гери", body="Хубав аромат.", rating=4),
    dict(product="atopi", name="Дора", body="Помогна за няколко дни.", rating=5),
]


class ReviewStats(unittest.TestCase):
    def test_counts(self):
        s = review_stats.stats([r for r in BANK if r["product"] == "acne"])
        self.assertEqual(s["n"], 4)
        self.assertEqual(s["five_pct"], 75)
        self.assertEqual(s["improve"], 3)  # изчист, разлика, по-спокой
        self.assertEqual((s["fast"], s["slow"], s["timed"]), (2, 1, 3))  # Вера е и бърза, и бавна → бърза
        self.assertEqual(s["fast_pct"], 67)
        self.assertFalse(s["time_claim_ok"])
        self.assertEqual([x["name"] for x in s["groups"]["slow"]], ["Бети"])
        self.assertEqual(s["groups"]["fast"][0]["match"], "за седмица")

    def test_ready_line_and_ratio(self):
        self.assertEqual(review_stats.ratio_words(109, 143), "3/4")
        self.assertEqual(review_stats.ratio_words(4, 5), "4/5")
        s = review_stats.stats([r for r in BANK if r["product"] == "acne"])
        self.assertIn("67% (2 от 3) промяна в първата седмица", review_stats.ready_line(s))

    def test_ro_stub_fails_clearly(self):
        with self.assertRaises(SystemExit):
            review_stats.stats(BANK, lang="ro")

    def test_cli_with_bank_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bank.json")
            json.dump(BANK, open(p, "w"), ensure_ascii=False)
            out = subprocess.run([sys.executable, os.path.join(ROOT, "agent", "review_stats.py"), "--client", "so_simple",
                                  "--product", "acne", "--bank", p, "--json"], capture_output=True, text=True, check=True).stdout
            self.assertEqual(json.loads(out)["n"], 4)


class Claims(unittest.TestCase):
    ROWS = [dict(title="Подарък", units=2000, net=0), dict(title=None, units=1700, net=400),
            dict(title="Серум", units=1900, net=200), dict(title="Мехлем при акне - ACNE GONE", units=1197, net=100),
            dict(title="Билков чай при Акне", units=87, net=7)]

    def test_rank_skips_gifts_and_empty(self):
        me, overall, among, group = claims.rank(self.ROWS, "ACNE GONE", ["Чай при Акне"])
        self.assertEqual((overall, among, len(group)), (2, 1, 2))

    def test_stock_wording(self):
        weekly, weeks, lines = claims.stock_wording(640, 1197, 90)
        self.assertAlmostEqual(weeks, 6.9, places=1)
        self.assertIn("над 1 100 продадени за 3 месеца", lines[0])
        self.assertTrue(any("Ограничено" in x for x in lines))
        self.assertEqual(len(claims.stock_wording(5000, 1197, 90)[2]), 1)

    def test_other_client_fails(self):
        with self.assertRaises(SystemExit):
            claims.gql("nordics", "{shop{name}}")
        with self.assertRaises(SystemExit):
            claims.gql("so_simple", "mutation{x}")


def img(src, w=300, h=300, nw=1000, nh=1000, clone=False, fit="cover", y=0):
    return dict(src=src, w=w, h=h, nw=nw, nh=nh, clone=clone, fit=fit, y=y, alt="")


class Media(unittest.TestCase):
    def test_norm_url_shopify(self):
        a = norm_url("//sosimplecosmetics.eu/cdn/shop/files/ba1_600x.jpg?v=123&width=800")
        b = norm_url("https://sosimplecosmetics.eu/cdn/shop/files/ba1.jpg?v=999")
        c = norm_url("https://SOSIMPLECOSMETICS.EU/cdn/shop/files/ba1_1200x1200@2x.jpg")
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertNotEqual(a, norm_url("https://sosimplecosmetics.eu/cdn/shop/files/ba2.jpg"))
        self.assertIsNone(norm_url("data:image/png;base64,xx"))

    def test_duplicates_ignore_icons_and_clones(self):
        u = "https://x.com/cdn/shop/files/ba1.jpg"
        self.assertEqual(len(duplicates([img(u + "?width=400"), img(u + "?width=800")])), 1)
        self.assertEqual(duplicates([img(u), img(u, clone=True)]), [])  # клонинг на слайдер (aria-hidden)
        self.assertEqual(duplicates([img("https://x.com/i.svg", 24, 24), img("https://x.com/i.svg", 24, 24)]), [])

    def test_rotation_and_crop(self):
        self.assertTrue(rotated(img("a", w=390, h=220, nw=1200, nh=1600)))   # портрет, показан легнал
        self.assertFalse(rotated(img("a", w=390, h=290, nw=1600, nh=1200)))  # същата ориентация
        self.assertTrue(cropped_thumb(img("a", w=32, h=32, nw=580, nh=1430)))  # бутилка в квадрат 32
        self.assertFalse(cropped_thumb(img("a", w=32, h=32, nw=580, nh=1430, fit="contain")))
        self.assertFalse(cropped_thumb(img("a", w=200, h=200, nw=580, nh=1430)))

    def test_analyze_levels(self):
        u = "https://x.com/a.jpg"
        f = analyze(dict(imgs=[img(u), img(u), img("b", w=32, h=32, nw=580, nh=1430)], over=[]), 390)
        self.assertEqual(sorted(x["kind"] for x in f), ["crop", "duplicate"])
        self.assertEqual([x["level"] for x in f if x["kind"] == "duplicate"], ["error"])


class AllowedMissing(unittest.TestCase):
    def test_scarcity_now_must_be_cloned(self):
        for t in ("Low stock: only 12 left", "Selling fast!", "Stock notice", "Недостиг на склад"):
            self.assertIsNone(ALLOWED_MISSING.search(t), t)

    def test_still_allowed(self):
        for t in ("Sold out 12x", "30-day money back guarantee", "Clinical study", "Countdown timer", "cured my acne"):
            self.assertIsNotNone(ALLOWED_MISSING.search(t), t)


if __name__ == "__main__":
    unittest.main()
