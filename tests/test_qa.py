import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent", "qa"))
from capture import build_sections, classify, heading_number
from compare import align, analyze, section_sim
from lint_copy import lint_text, load_rules, html_text, dedupe_cyr
from check_reviews import parse_card, match_review, name_score, text_score, inline_quotes


def sec(y, h, type_="text", img=0, li=0, rep=0, heading="", num=None, button=0):
    return dict(y=y, h=h, type=type_, img=img, bgimg=0, video=0, li=li, repeat=rep, button=button, heading=heading, num=num)


class Sections(unittest.TestCase):
    def test_heading_number(self):
        self.assertEqual(heading_number("3. Най-простата грижа"), 3)
        self.assertEqual(heading_number("Причина №7: бариерата"), 7)
        self.assertEqual(heading_number("Reason 10 why"), 10)
        self.assertIsNone(heading_number("Над 35 000 поръчки"))
        self.assertIsNone(heading_number("6 БИЛКИ + 5 МАСЛА"))
        self.assertIsNone(heading_number("13,00 € на стик"))
        self.assertEqual(heading_number("#2 Нежно"), 2)

    def test_build_sections_cuts_on_headings_and_merges_small(self):
        raw = dict(H=3000, y0=0, y1=3000, heads=[dict(y=20, t="Hero", tag="h1", fs=32), dict(y=1000, t="1. Едно", tag="h2", fs=24),
                                              dict(y=2000, t="FAQ", tag="h2", fs=24)],
                   bands=[], items=[["img", 500, 300], ["li", 1200, 30], ["li", 1300, 30], ["li", 1400, 30],
                                    ["details", 2100, 40], ["details", 2200, 40], ["text", 1100, 50, "Inter", "текст"]])
        s = build_sections(raw)
        self.assertEqual([x["y"] for x in s], [0, 1000, 2000])  # 0-20 е под 60 px и отива към следващата
        self.assertEqual(s[0]["type"], "image")
        self.assertEqual(s[1]["type"], "list")
        self.assertEqual(s[1]["num"], 1)
        self.assertEqual(s[2]["type"], "faq")
        self.assertEqual(s[1]["fonts"], ["Inter"])

    def test_classify_offer(self):
        s = dict(img=1, bgimg=0, video=0, button=1, li=0, details=0, input=0, star=0, price=2, question=0, repeat=0, text_len=200)
        self.assertEqual(classify(s), "offer")


class Alignment(unittest.TestCase):
    def test_identical_sequences_align_one_to_one(self):
        A = [sec(0, 800, "image", img=1), sec(800, 1200, "list", li=5), sec(2000, 600, "offer"), sec(2600, 400, "faq")]
        path, _ = align(A, A, 3000, 3000)
        self.assertEqual([(i, j) for i, j, _ in path], [(0, 0), (1, 1), (2, 2), (3, 3)])
        r = analyze(A, A, 3000, 3000)
        self.assertGreaterEqual(r["score"], 95)
        self.assertEqual(r["missing"], [])

    def test_missing_reasons_detected(self):
        # 10 причини в оригинала, 8 в клонинга
        A = [sec(0, 600, "image", img=1, heading="Hero")] + [sec(600 + k * 500, 500, "image", img=1, heading=f"{k + 1}. X", num=k + 1) for k in range(10)]
        B = [sec(0, 600, "image", img=1, heading="Хиро")] + [sec(600 + k * 625, 625, "image", img=1, heading=f"{k + 1}. Y", num=k + 1) for k in range(8)]
        r = analyze(A, B, 5600, 5600)
        self.assertEqual(r["numbered"], {"orig": 10, "clone": 8})
        self.assertEqual(len(r["missing"]), 2)
        self.assertEqual(r["sections_orig"] - r["sections_clone"], 2)
        self.assertLess(r["score"], 95)

    def test_item_count_mismatch_reported(self):
        A = [sec(0, 1000, "list", li=10)]
        B = [sec(0, 1000, "list", li=8)]
        r = analyze(A, B, 1000, 1000)
        self.assertEqual(r["diffs"][0]["counts"], [("точки в списък", 10, 8)])

    def test_similarity_prefers_same_type_and_position(self):
        a = sec(0, 500, "offer")
        self.assertGreater(section_sim(a, sec(0, 500, "offer"), 1000, 1000), section_sim(a, sec(500, 500, "faq"), 1000, 1000))


class Lint(unittest.TestCase):
    def setUp(self):
        self.rules = load_rules("so_simple")

    def ids(self, text, lang=None):
        return [f["rule"] for f in lint_text(text, self.rules, lang) if f["level"] == "error"]

    def test_forbidden(self):
        self.assertIn("em_dash", self.ids("Кожата — по-спокойна"))
        self.assertIn("en_dash_as_dash", self.ids("Кожата – по-спокойна"))
        self.assertNotIn("en_dash_as_dash", self.ids("2–3 седмици"))
        self.assertIn("illustrative", self.ids("Илюстративна снимка"))
        self.assertIn("ad_label", self.ids("Рекламна публикация на So Simple"))
        self.assertIn("cure", self.ids("Мехлемът излекува акнето"))
        self.assertIn("natural_100", self.ids("100% натурални съставки"))
        self.assertIn("guarantee", self.ids("Гаранция 30 дни"))
        self.assertIn("money_back", self.ids("или парите обратно"))
        self.assertEqual(self.ids("Подбрани съставки, видимо по-гладка кожа."), [])

    def test_negation_is_warning(self):
        f = lint_text("Това е козметика, не лекува.", self.rules)
        self.assertEqual([x["level"] for x in f if x["rule"] == "cure"], ["warn"])

    def test_cyrillic_on_ro(self):
        f = dedupe_cyr(lint_text("Pielea este calmă. Отзиви", self.rules, lang="ro"))
        self.assertTrue(any(x["rule"] == "cyrillic_on_ro" for x in f))
        self.assertFalse(any(x["rule"] == "cyrillic_on_ro" for x in lint_text("Pielea este calmă.", self.rules, lang="ro")))

    def test_nordics_peroxide(self):
        f = lint_text("Избелва с пероксид за 3 дни", load_rules("nordics"))
        self.assertIn("peroxide_whitening", [x["rule"] for x in f])

    def test_html_alt(self):
        text, alts = html_text('<p>Текст</p><img alt="Илюстративна снимка"><script>var a="—"</script>')
        self.assertNotIn("—", text)
        self.assertEqual(alts, ["Илюстративна снимка"])


BANK = [
    dict(product="acne-gone-mehlem-pri-akne", name="Красимира Спасова", body="Синът ми е тийн и има много черни твърди точки около носа и брадичката. Само от едно нанасяне на чиста кожа първата вечер имаше разлика на сутринта."),
    dict(product="acne-gone-mehlem-pri-akne", name="Д. Димитрова", body="Доволна съм от мехлема. Периодично се появяват петънца по кожата на бебето ми."),
    dict(product="mehlem-pri-atopichen-dermatit-atopi-gone", name="Радостина Цветанова", body="Детето ми е почти на 3 г. и се борим с ужасния атопичен дерматит още от родилното.", language="bg"),
]


class Reviews(unittest.TestCase):
    def test_parse_card_formats(self):
        n, b, _ = parse_card("★★★★★\n„Доволна съм от мехлема. Периодично се появяват петънца“\n\nД. Димитрова\n\n17.06.2025")
        self.assertEqual(n, "Д. Димитрова")
        self.assertTrue(b.startswith("Доволна"))
        n, _, _ = parse_card("ДД\nД. Димитрова\nРаботи!\n17.06.2025\n★★★★★\nДоволна съм от мехлема, наистина.")
        self.assertEqual(n, "Д. Димитрова")

    def test_match_ok_excerpt(self):
        st, r, ts, ns = match_review(["Красимира Спасова"], "Синът ми е тийн и има много черни твърди точки около носа и брадичката.", BANK)
        self.assertEqual(st, "OK")

    def test_fake_review_not_in_bank(self):
        st, *_ = match_review(["Мария Петрова"], "Този мехлем ми промени живота, препоръчвам го на всички приятелки.", BANK)
        self.assertEqual(st, "НЕ Е В БАНКАТА")

    def test_real_text_wrong_name(self):
        st, *_ = match_review(["Ивана Колева"], "Доволна съм от мехлема. Периодично се появяват петънца по кожата на бебето ми.", BANK)
        self.assertEqual(st, "ДРУГО ИМЕ")

    def test_translation_flagged_for_manual_check(self):
        st, r, *_ = match_review(["Radostina Tsvetanova"], "Copilul meu are aproape 3 ani și ne luptăm cu dermatita atopică încă de la naștere.", BANK)
        self.assertEqual(st, "ПРЕВОД — ПРОВЕРКА НА РЪКА")
        self.assertEqual(r["name"], "Радостина Цветанова")

    def test_name_and_text_scores(self):
        self.assertGreaterEqual(name_score("Мария К.", "Мария Колева"), 0.75)
        self.assertLess(name_score("Мария", "Ивана"), 0.75)
        self.assertEqual(text_score("кратко", "кратко"), 0.0)

    def test_inline_quotes(self):
        q = inline_quotes("„Стикът е за сина ми, действа омекотяващо и успокояващо.“ пише Таня Атанасова.")
        self.assertEqual(q[0][0], "Таня Атанасова")


if __name__ == "__main__":
    unittest.main()
