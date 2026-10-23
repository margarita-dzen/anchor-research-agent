import datetime, json, os, sys, tempfile, unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "agent"))
sys.path.insert(0, os.path.join(ROOT, "agent", "qa"))
sys.path.insert(0, os.path.join(ROOT, "agent", "adlib"))
import evidence
import feedback
import clone_mode
import review_bank
import import_playbook_ads as imp
from verify_cart import parse_anchor_cart, parse_shopify_permalink, cart_links, compare_woo


class Velocity(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(evidence.velocity(2, 5, 10, 90), 6 + 5 + 3 + 5)
        self.assertEqual(evidence.velocity(0, 0, 3, 30), 0.9)

    def test_in_rows_not_in_score(self):
        today = datetime.date(2026, 10, 23)
        ads = [dict(landing_url=f"https://x.com/p", active=True, duplicates=1, days_running=100,
                    first_seen=str(today - datetime.timedelta(days=d)), meta_ad_id=str(d)) for d in (1, 2, 3, 40)]
        passed, _ = evidence.aggregate(ads, today, blocklist={})
        r = passed[0]
        self.assertEqual((r["new_ads_7d"], r["new_ads_30d"]), (3, 3))
        self.assertTrue(r["scaling_now"])
        self.assertNotIn("velocity", r["evidence_breakdown"])


class ImportPlaybookAds(unittest.TestCase):
    def test_convert_and_merge(self):
        today = datetime.date(2026, 10, 23)
        a = dict(id="111", api="TT", advertiser="Zahnheld", page_id="9", days=120, countries=["DE"], fmt="VIDEO",
                 variants=4, title="T", body="Kinder lieben es", link="https://www.zahnheld.de/pages/kids?utm=1", media="m.mp4",
                 problems=["kids"], searched=["AT"])
        r = imp.convert(a, "kids", today)
        self.assertEqual(r["first_seen"], "2026-06-25")
        self.assertEqual((r["format"], r["duplicates"], r["domain"]), ("video", 4, "zahnheld.de"))
        self.assertEqual(r["countries"], ["AT", "DE"])
        self.assertTrue(r["active"])
        merged, added = imp.merge([dict(meta_ad_id="111", domain="zahnheld.de", primary_text="Kinder lieben es")], [r, dict(r, meta_ad_id="222"), dict(r, meta_ad_id="333", primary_text="друго")])
        # 111 вече е там; 222 е същият текст на същия домейн → дубликат; 333 е нов
        self.assertEqual([x["meta_ad_id"] for x in added], ["333"])
        self.assertEqual(len(merged), 2)


class VerifyCart(unittest.TestCase):
    def test_parse(self):
        u = "https://wearenordics.com/?anchor_cart=140558:1,208899:2:color=pink&anchor_funnel=x"
        self.assertEqual(parse_anchor_cart(u), [(140558, 1, ""), (208899, 2, "color=pink")])
        self.assertEqual(parse_shopify_permalink("https://s.com/cart/111:1,222:3?ref=a"), [(111, 1), (222, 3)])

    def test_links_from_html(self):
        html = '<a href="https://wearenordics.com/?anchor_cart=1:1&amp;a=b">x</a><a href="/cart/5:1">y</a><a href="/p">z</a>' \
               '<a href="https://wearenordics.com/?anchor_cart=1:1&amp;a=b">dup</a>'
        self.assertEqual(cart_links(html, "https://s.com/"), ["https://wearenordics.com/?anchor_cart=1:1&a=b", "https://s.com/cart/5:1"])

    def test_compare(self):
        ok, notes = compare_woo([(140558, 1, "")], [dict(id=140558, quantity=1)])
        self.assertTrue(ok)
        ok, notes = compare_woo([(140558, 2, ""), (9, 1, "")], [dict(id=140558, quantity=1)])
        self.assertFalse(ok)
        self.assertEqual(len(notes), 2)


class Feedback(unittest.TestCase):
    def test_parse_md(self):
        md = "# X\n## Шрифт\n1. Шрифтовете на Nordics.\n2. Бутони:\n   - главни букви;\n## Проверка\n- QA: python3 run_qa.py\n21. Без FIG.\n"
        self.assertEqual(feedback.parse_md(md), ["Шрифтовете на Nordics.", "Бутони:; главни букви;", "Без FIG."])

    def test_answers(self):
        with tempfile.TemporaryDirectory() as td:
            run, src = os.path.join(td, "run"), os.path.join(td, "src")
            os.makedirs(run), os.makedirs(src)
            json.dump(dict(note="да", status=None), open(os.path.join(src, "q-bundles.json"), "w"))
            json.dump(dict(note="", status=None), open(os.path.join(src, "q-empty.json"), "w"))
            json.dump(dict(note="ок", status="approved"), open(os.path.join(src, "page-a.json"), "w"))
            json.dump(dict(note="бутонът с главни букви", status="change"), open(os.path.join(src, "page-b.json"), "w"))
            feedback.ingest(run, src)
            rows = [json.loads(l) for l in open(os.path.join(run, "feedback.jsonl"))]
            self.assertEqual(sorted((r["item"], r["kind"]) for r in rows), [("page-b", "change"), ("q-bundles", "answer")])
            self.assertIn("бутон / CTA / количка", [r for r in rows if r["item"] == "page-b"][0]["cats"])


class CloneOverrides(unittest.TestCase):
    def test_nordics(self):
        o = clone_mode.overrides("nordics")
        self.assertEqual((o["fonts"], o["colors"], o["italic"]), ("brand", "brand", False))
        self.assertEqual(clone_mode.overrides("nobody"), {})


class BankRating(unittest.TestCase):
    def test_keeps_rating(self):
        base = dict(product="p", name="Ана", body="Супер", date=None, language=None, pictures=[], videos=[])
        bank = review_bank.merge([dict(base, rating=None, source="docx"), dict(base, rating=5, source="woo")])
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank[0]["rating"], 5)


if __name__ == "__main__":
    unittest.main()
