"""Цялото QA на клонинг в един Markdown доклад: сходство с оригинала + копи/техника + отзиви.

    python3 agent/qa/run_qa.py <оригинал: URL или папка src/> <клонинг: URL> --client so_simple \
        [--lang bg|ro] [--bank ~/Clients/So-Simple/reviews/bank.json] [--product atopi] \
        [--out qa_out/<име>] [--threshold 85] [--widths 390,1440] [--max-height 16000]

Вердикт „ГОТОВО“ само ако: оценката за сходство >= прага, 0 грешки в копито/техниката, 0 отзива извън банката
и 0 грешки в снимките (check_media.py: повторена или завъртена снимка; изрязване и текст върху продукта са за проверка).
Пише в --out: report.md, qa.json, cmp_<w>_<nn>.jpg (оригинал | клонинг), original/ и clone/ (снимки, outline, текст).
Банката на отзивите се взима от agent/config/clients.json (reviews.bank), ако не е подадена.
"""
import argparse, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import compare as cmp_mod
import lint_copy
import check_reviews
import check_media


def client_bank(client):
    try:
        c = json.load(open(os.path.join(HERE, "..", "config", "clients.json")))
        return (c.get(client, {}).get("reviews") or {}).get("bank")
    except Exception:
        return None


def slug(url):
    s = re.sub(r"^https?://", "", url).split("?")[0].strip("/")
    return re.sub(r"[^\w.-]+", "_", s)[-60:] or "page"


# секции, които правилата задължават да махнем (гаранция, проучване, измислен лекар, знаменитости, таймер, абонамент):
# недостигът („low stock“, „selling fast“) вече НЕ е тук: клонира се, когато е вярно (claims.py stock, absolute-clone.md §8.2).
# липсата им не е грешка на клонинга. Ако всичко липсващо е от тях, прагът пада до FLOOR.
ALLOWED_MISSING = re.compile(r"geld.?zur|money.?back|guarantee|garan|гаранц|risk.?free|clinical|klinisch|study|studie|проучване|"
                             r"\bdr\.|doctor|arzt|dermatolog|лекар|celebrit|famous|знаменит|timer|countdown|таймер|subscri|abonn|абонам|"
                             r"impressum|imprint|sichere transaktion|secure checkout|hergestellt|made in|sold out|deal ending|cured", re.I)
FLOOR = 70


def allowed_missing(cres):
    """Връща (всички липсващи са позволени?, списък липсващи с текст) по най-тясната ширина."""
    w = cres["widths"][sorted(cres["widths"], key=lambda k: int(k))[0]]
    secs = w.get("sections_original") or []
    miss = [secs[i] for i in w.get("missing", []) if i < len(secs)]
    rows = [((m.get("heading") or "") + " " + (m.get("text") or ""))[:120] for m in miss]
    ok = all(ALLOWED_MISSING.search(r) or not r.strip() for r in rows)
    return ok, rows


def md_report(original, clone, args, cres, lres, rres, mres=None):
    all_allowed, missing_rows = allowed_missing(cres)
    ok_cmp = cres["score"] >= args.threshold or (all_allowed and cres["score"] >= FLOOR)
    ok_lint = lres["errors"] == 0
    ok_rev = rres is None or rres["bad"] == 0
    ok_media = mres is None or mres["errors"] == 0
    ready = ok_cmp and ok_lint and ok_rev and ok_media
    L = [f"# QA на клонинг: {'ГОТОВО' if ready else 'НЕ Е ГОТОВО'}", ""]
    L.append(f"- Оригинал: {original}")
    L.append(f"- Клонинг: {clone}")
    L.append(f"- Клиент: {args.client}, език: {args.lang or 'bg'}, дата: {datetime.date.today().isoformat()}")
    L.append("")
    L.append("| Проверка | Резултат | Минава |")
    L.append("|---|---|---|")
    L.append(f"| Сходство с оригинала | {cres['score']}/100 (праг {args.threshold}; {FLOOR}, ако липсва само забраненото от правилата) | {'да' if ok_cmp else 'НЕ'} |")
    L.append(f"| Копи и техника | {lres['errors']} грешки, {lres['warnings']} за проверка | {'да' if ok_lint else 'НЕ'} |")
    if rres is None:
        L.append("| Отзиви | не е проверено (няма банка) | ? |")
    else:
        L.append(f"| Отзиви | {len(rres['reviews'])} на страницата, {rres['bad']} извън банката, {rres['manual']} за ръчна проверка | {'да' if ok_rev else 'НЕ'} |")
    if mres is None:
        L.append("| Снимки | не е проверено | ? |")
    else:
        L.append(f"| Снимки | {mres['errors']} грешки (повторени/завъртени), {mres['warnings']} за проверка | {'да' if ok_media else 'НЕ'} |")
    L.append("")
    if missing_rows:
        L.append("Липсващи секции: " + "; ".join(("[позволено] " if ALLOWED_MISSING.search(r) else "[ГРЕШКА] ") + r.strip()[:70] for r in missing_rows))
        L.append("")
    L.append("## 1. Сходство с оригинала (секция по секция)")
    L.append("")
    L.append("```")
    L.append(cres["report"])
    L.append("```")
    for w, r in cres["widths"].items():
        if r.get("images"):
            L.append(f"Снимки едно до друго ({w} px): " + ", ".join(os.path.basename(p) for p in r["images"][:60]))
            L.append("")
    L.append("## 2. Копи и техника")
    L.append("")
    L.append("```")
    L.append(lint_copy.text_report(lres))
    L.append("```")
    L.append("")
    L.append("## 3. Отзиви срещу банката")
    L.append("")
    if rres is None:
        L.append("Няма банка с отзиви за клиента.")
    else:
        L.append("```")
        L.append(check_reviews.text_report(rres))
        L.append("```")
    L.append("")
    L.append("## 4. Снимки (повторения, завъртане, изрязване, текст върху продукта)")
    L.append("")
    if mres is None:
        L.append("Не е проверено.")
    else:
        L.append("```")
        L.append(check_media.text_report(mres))
        L.append("```")
    return "\n".join(L) + "\n", ready


def main():
    ap = argparse.ArgumentParser(description="QA на клонинг: сходство + копи + отзиви → report.md")
    ap.add_argument("original")
    ap.add_argument("clone")
    ap.add_argument("--client", default="so_simple")
    ap.add_argument("--lang", default=None)
    ap.add_argument("--bank", default=None)
    ap.add_argument("--product", default=None)
    ap.add_argument("--scope", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--threshold", type=float, default=85)
    ap.add_argument("--widths", default="390,1440")
    ap.add_argument("--max-height", type=int, default=None)
    a = ap.parse_args()
    out = a.out or os.path.join("qa_out", slug(a.clone))
    os.makedirs(out, exist_ok=True)
    widths = [int(x) for x in a.widths.split(",")]
    print("1/4 сравнение с оригинала…", flush=True)
    cres = cmp_mod.compare(a.original, a.clone, out, widths=widths, threshold=a.threshold, max_height=a.max_height)
    print("2/4 копи и техника…", flush=True)
    lres = lint_copy.lint(a.clone, a.client, lang=a.lang, scope=a.scope)
    bank = a.bank or client_bank(a.client)
    rres = None
    if bank and os.path.exists(os.path.expanduser(bank)):
        print("3/4 отзиви…", flush=True)
        rres = check_reviews.check(a.clone, bank, a.product)
    mres = None
    if re.match(r"https?://", a.clone):
        print("4/4 снимки…", flush=True)
        mres = check_media.check(a.clone, widths)
    md, ready = md_report(a.original, a.clone, a, cres, lres, rres, mres)
    open(os.path.join(out, "report.md"), "w").write(md)
    dump = dict(compare=json.load(open(os.path.join(out, "compare.json"))), lint=lres, reviews=rres, media=mres, ready=ready)
    json.dump(dump, open(os.path.join(out, "qa.json"), "w"), ensure_ascii=False, indent=1)
    print(md)
    print(f"Докладът: {os.path.join(out, 'report.md')}")
    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()
