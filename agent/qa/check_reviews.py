"""Всеки отзив на страницата трябва да е истински: име + текст от банката с отзиви на клиента.

    python3 agent/qa/check_reviews.py <url | page.html> --bank ~/Clients/So-Simple/reviews/bank.json [--product atopi] [--json out.json]

Намира блоковете, които приличат на отзив (звезди ★ / клас star|rating|review|testimonial / цитат в кавички + кратко име),
вади името и текста и ги търси в банката (agent/review_bank.py: [{product, name, body, rating, date, pictures, videos, sources}]).
Сравнението е размито, по нормализиран текст (без пунктуация, главни букви и емоджи), и хваща съкратени цитати.

Статуси:
  OK                          име и текст са в банката (текстът може да е съкратен)
  РЕДАКТИРАН                  името е в банката, текстът е близък, но е променен (провери дословността)
  ПРЕВОД — ПРОВЕРКА НА РЪКА   името съвпада (с транслитерация), текстът е на друг език/азбука
  ДРУГО ИМЕ                   текстът е в банката, но под друго име
  НЕ Е В БАНКАТА              нито текстът, нито името (измислен или чужд отзив)
Изходен код 1, ако има ДРУГО ИМЕ или НЕ Е В БАНКАТА.
"""
import argparse, json, os, re, sys, time, unicodedata
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TRANSLIT = dict(zip("абвгдежзийклмнопрстуфхцчшщъьюяѝ",
                    ["a", "b", "v", "g", "d", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
                     "f", "h", "ts", "ch", "sh", "sht", "a", "y", "yu", "ya", "i"]))
CYR = re.compile(r"[Ѐ-ӿ]")
LAT = re.compile(r"[A-Za-z]")
NOISE_LINE = re.compile(r"^(?:[★☆⭐✩✪\s\d.,/()]+|проверен купувач|потвърден купувач|verified( buyer| purchase)?|"
                        r"cumpărător verificat|verifizierter kauf|истинска снимка.*|real photo.*|показване на още|виж още|"
                        r"read more|прочети още|helpful.*|полезно.*|\d+\s*(дни|days|zile|седмици)\s*(преди|ago)?|"
                        r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})$", re.I)
NAME_RE = re.compile(r"^[^\W\d_][^\d\n]{0,38}$")

EXTRACT_JS = r"""() => {
  const root = document.querySelector('[data-qa-scroller]') || document.body;
  const shown = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const ownText = e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').trim();
  const starAnchors = [], quoteAnchors = [];
  for (const e of root.querySelectorAll('*')) {
    if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(e.tagName) || !shown(e)) continue;
    const cls = String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || '') + ' ' + (e.id || '');
    const t = ownText(e);
    if ((t.match(/[★⭐]/g) || []).length >= 3 || (/(^|[-_ ])(stars?|rating|jdgm-rev__rating)([-_ ]|$)/i.test(cls) && !e.closest('[data-qa-star]'))) {
      e.setAttribute('data-qa-star', '1'); starAnchors.push(e);
    } else if (/^[„"“«”]/.test(t) && t.length >= 40) quoteAnchors.push(e);
    else if (e.tagName === 'BLOCKQUOTE' || /testimonial|review-body|jdgm-rev__body|quote/i.test(cls)) quoteAnchors.push(e);
  }
  const count = (el, list) => list.reduce((n, a) => n + (el.contains(a) ? 1 : 0), 0);
  const cards = [];
  const climb = (a, list) => {
    let el = a;
    while (el.parentElement && el.parentElement !== root && count(el.parentElement, list) === 1 && (el.parentElement.innerText || '').length < 1500) el = el.parentElement;
    return el;
  };
  for (const a of starAnchors) cards.push(climb(a, starAnchors));
  const inCard = e => cards.some(c => c.contains(e));
  const starCards = [...new Set(cards)].filter(c => !cards.some(o => o !== c && c.contains(o)));
  // цитати в кавички: целият абзац, за да се види името („… пише Таня А.“)
  const quoteCards = [...new Set(quoteAnchors.filter(e => !inCard(e)).map(e => e.closest('p, li, blockquote, figure') || e))]
    .filter((c, i, arr) => !arr.some(o => o !== c && o.contains(c)));
  const uniq = starCards.map(c => [c, 'card']).concat(quoteCards.map(c => [c, 'quote']));
  const byClass = (c, re) => { const e = [...c.querySelectorAll('*')].find(x => re.test(String(x.className))); return e ? e.innerText.trim() : ''; };
  return uniq.filter(([c]) => !c.querySelector('h1, h2')).map(([c, kind]) => ({
    kind: kind,
    y: Math.round(c.getBoundingClientRect().top + scrollY),
    text: c.innerText,
    name_hint: byClass(c, /author|name|reviewer/i),
    body_hint: byClass(c, /rev__body|review-body|review__body|content|quote|text/i),
    imgs: c.querySelectorAll('img').length,
  }));
}"""


# ---------- чиста логика ----------

def strip_accents(s):
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def norm(s):
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.U)
    s = re.sub(r"_", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def translit(s):
    return strip_accents("".join(TRANSLIT.get(ch, ch) for ch in norm(s)))


def script_of(s):
    c, l = len(CYR.findall(s or "")), len(LAT.findall(s or ""))
    return "cyr" if c > l else "lat"


def coverage(a, b):
    """Каква част от a се намира в b (по съвпадащи блокове)."""
    if not a or not b:
        return 0.0
    sm = SequenceMatcher(None, a, b, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks() if m.size >= 4) / float(len(a))


def text_score(page, bank):
    a, b = norm(page), norm(bank)
    if len(a) < 15 or len(b) < 15:
        return 0.0
    wa, wb = set(a.split()), set(b.split())
    if len(wa & wb) / float(max(1, min(len(wa), len(wb)))) < 0.25:
        return 0.0
    c1 = coverage(a, b)
    c2 = coverage(b, a) if len(b) >= 30 else 0.0
    return round(max(c1, c2), 3)


def name_score(a, b):
    """0..1: същото име (с транслитерация), или същото първо име + инициал."""
    ta, tb = translit(a).split(), translit(b).split()
    if not ta or not tb:
        return 0.0
    if ta == tb:
        return 1.0
    ra = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    if ta[0] == tb[0] or SequenceMatcher(None, ta[0], tb[0]).ratio() >= 0.85:
        if len(ta) == 1 or len(tb) == 1:
            return max(ra, 0.75)
        if ta[1][0] == tb[1][0]:
            return max(ra, 0.85)
    return round(ra, 3)


def parse_card(text, name_hint="", body_hint=""):
    """Текст на карта → (име, текст на отзива, всички кандидати за име)."""
    lines = [l.strip().strip("„“\"”«»").strip() for l in (text or "").split("\n")]
    lines = [l for l in lines if l and not NOISE_LINE.match(l)]
    names = []
    if name_hint and len(name_hint) <= 40:
        names.append(name_hint.strip())
    for l in lines:
        head = l.split(",")[0].strip()
        if len(l) <= 60 and len(head) <= 40 and NAME_RE.match(head) and not re.search(r"[!?:;…]|\.\s*$(?<!\b\w\.)", head):
            words = head.split()
            caps = all(w[0].isupper() for w in words if w[0].isalpha())
            if 1 <= len(words) <= 4 and caps and not (len(words) == 1 and l.isupper() and len(l) <= 3):
                names.append(l.split(",")[0].strip())
    body = body_hint.strip() if body_hint and len(body_hint) >= 25 else ""
    if not body:
        longs = [l for l in lines if len(l) >= 25]
        body = "\n".join(longs)
    return (names[0] if names else ""), body, names


QUOTE_RE = re.compile(r"[„\"“«]([^„“”\"«»]{25,})[“”\"»]")
CAP_NAME = re.compile(r"(?<![\w])([A-ZА-ЯĂÂÎȘȚ][\w’'-]+(?:\s+[A-ZА-ЯĂÂÎȘȚ][\w’'.-]*){0,2})")


def inline_quotes(text):
    """Цитати в абзац: [(име до цитата или '', цитат)]. Името е първата дума(и) с главна буква след цитата
    („… пише Таня Атанасова“), иначе преди него."""
    out = []
    for m in QUOTE_RE.finditer(text or ""):
        after = text[m.end():m.end() + 60]
        before = text[max(0, m.start() - 60):m.start()]
        name = ""
        mm = CAP_NAME.search(after[:35])
        if mm and len(mm.group(1).split()) >= 1 and not re.match(r"^\s*[.!?]", after):
            name = mm.group(1)
        else:
            mb = list(CAP_NAME.finditer(before))
            if mb:
                name = mb[-1].group(1)
        out.append((name.strip(" ."), m.group(1).strip()))
    return out


def match_review(names, body, bank, product=None):
    """Най-доброто съвпадение в банката и статус."""
    pool = [r for r in bank if not product or product in (r.get("product") or "")] or bank
    best_t, best_r = 0.0, None
    for r in pool:
        s = text_score(body, r.get("body") or "")
        if s > best_t:
            best_t, best_r = s, r
    if best_r is None:  # текстът не е в продуктовия пул: търси в цялата банка
        for r in bank:
            s = text_score(body, r.get("body") or "")
            if s > best_t:
                best_t, best_r = s, r
    nm = max((name_score(n, best_r["name"]) for n in names), default=0.0) if best_r else 0.0
    if best_r and best_t >= 0.85 and nm >= 0.75:
        return "OK", best_r, best_t, nm
    if best_r and best_t >= 0.6 and nm >= 0.75:
        return "РЕДАКТИРАН", best_r, best_t, nm
    if best_r and best_t >= 0.85 and not names:
        return "БЕЗ ИМЕ (текстът е в банката)", best_r, best_t, nm
    if best_r and best_t >= 0.85:
        return "ДРУГО ИМЕ", best_r, best_t, nm
    # по име: превод или чужд текст
    by_name = []
    for r in bank:
        ns = max((name_score(n, r.get("name") or "") for n in names), default=0.0)
        if ns >= 0.85:
            by_name.append((ns, r))
    if by_name:
        page_script = script_of(body)
        for ns, r in sorted(by_name, key=lambda x: -x[0]):
            rb = r.get("body") or ""
            ratio = len(body) / float(max(1, len(rb)))
            if script_of(rb) != page_script or (r.get("language") and r.get("language") not in ("bg",) and page_script == "cyr"):
                if 0.4 <= ratio <= 2.5:
                    return "ПРЕВОД — ПРОВЕРКА НА РЪКА", r, text_score(body, rb), ns
        ns, r = by_name[0]
        return "НЕ Е В БАНКАТА", r, text_score(body, r.get("body") or ""), ns
    return "НЕ Е В БАНКАТА", best_r, best_t, nm


# ---------- браузър ----------

def extract(target):
    if os.path.exists(os.path.expanduser(target)):
        url = "file://" + os.path.abspath(os.path.expanduser(target))
    else:
        url = target
    from playwright.sync_api import sync_playwright
    from capture import open_page, lazy_scroll
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)  # само headless
        try:
            ctx, page, sc = open_page(b, url, 390)
            lazy_scroll(page, scroller=bool(sc))
            # отваря „виж още“ в слайдери/акордеони няма: проверяват се видимите карти
            cards = page.evaluate(EXTRACT_JS)
            ctx.close()
        finally:
            b.close()
    return cards


def check(target, bank_path, product=None):
    bank = json.load(open(os.path.expanduser(bank_path)))
    cards = extract(target)
    rows = []
    items = []
    for c in cards:
        if c.get("kind") == "quote":
            for name, body in inline_quotes(c["text"]):
                items.append((c, name, body, [name] if name else []))
        else:
            name, body, names = parse_card(c["text"], c.get("name_hint", ""), c.get("body_hint", ""))
            items.append((c, name, body, names))
    for c, name, body, names in items:
        if len(body) < 25:
            continue  # не е отзив (байлайн със звезди, рейтинг без текст)
        status, r, ts, ns = match_review(names, body, bank, product)
        rows.append(dict(y=c["y"], name=name, body=body[:400], status=status, text_score=ts, name_score=ns,
                         bank_name=(r or {}).get("name"), bank_product=(r or {}).get("product"),
                         bank_body=((r or {}).get("body") or "")[:200], bank_sources=(r or {}).get("sources"),
                         imgs=c.get("imgs", 0)))
    bad = [x for x in rows if x["status"] in ("НЕ Е В БАНКАТА", "ДРУГО ИМЕ")]
    return dict(target=target, bank=bank_path, reviews=rows, bad=len(bad),
                manual=sum(1 for x in rows if x["status"].startswith(("ПРЕВОД", "РЕДАКТИРАН", "БЕЗ ИМЕ"))))


def text_report(res):
    L = [f"Отзиви: {len(res['reviews'])} на страницата, {res['bad']} проблемни, {res['manual']} за ръчна проверка"]
    for x in res["reviews"]:
        mark = {"OK": "ok", "РЕДАКТИРАН": "??", "ДРУГО ИМЕ": "!!", "НЕ Е В БАНКАТА": "!!"}.get(x["status"], "??")
        line = f"  {mark} {x['status']}: {x['name'] or '(без име)'} „{x['body'][:70].replace(chr(10), ' ')}…“ (y={x['y']})"
        if x["status"] != "OK" and x["bank_name"]:
            line += f"\n      най-близко в банката: {x['bank_name']} [{x['bank_product']}] текст {x['text_score']}, име {x['name_score']}"
        L.append(line)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Отзивите на страницата срещу банката с истински отзиви.")
    ap.add_argument("target", help="URL или HTML файл")
    ap.add_argument("--bank", default="~/Clients/So-Simple/reviews/bank.json")
    ap.add_argument("--product", default=None, help="част от handle-а на продукта (напр. atopi, acne) за по-точно търсене")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    res = check(a.target, a.bank, a.product)
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    print(text_report(res))
    sys.exit(1 if res["bad"] else 0)


if __name__ == "__main__":
    main()
