"""Числа за твърденията на страницата, сметнати от банката с истински отзиви (absolute-clone.md §8.2).

    python3 agent/review_stats.py --client so_simple --product acne-gone-mehlem-pri-akne [--lang bg] [--bank <bank.json>] [--json]

Дава: брой отзиви, % 5 звезди, дял с описано подобрение, дял с промяна в първата седмица
(от отзивите, които посочват срок) и за всяка група имената + намерената фраза, за да се провери на ръка.
Отзив с бърз и бавен срок се брои като бърз. Срок („7 дни“) се ползва само при поне MIN_FAST бързи отзива.
Банката се взима от agent/config/clients.json (reviews.bank), ако не е подадена.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENTS = os.path.join(HERE, "config", "clients.json")
MIN_FAST = 10

# регулярни изрази по език; базата (bg) дава за ACNE GONE 143 отзива, 100% 5★, 109 подобрение, 21 бързи срещу 16 бавни
PATTERNS = {
    "bg": dict(
        improve=r"подобр|изчез|намал|изчист|по-спокой|успокоя|успокоение|гладк|резултат|ефект|работи|действа|помогна|разлика|избледн|"
                r"чист|отърва|завяхна|промяна|няма проблеми|го няма|вече го няма|разпознаваем|чудеса|премахна|мека и свежа|бързо минат|минат по",
        fast=r"първата седмица|първа седмица|за седмица|над седмица|около седмица|първия ден|първите дни|на сутринта|сутрин е|три дни|"
             r"два три дни|няколко дни|първата вечер|още от първ|няколко намазвания|първия път|от едно нанасяне",
        slow=r"2 седмици|две седмици|3 седмици|три седмици|2-3 седмици|1-2 седмици|месец|20 дни|няколко седмици",
    ),
    # TODO: румънски изрази, когато RO отзивите в банката станат достатъчно
    "ro": dict(improve=None, fast=None, slow=None),
}


def client_bank(client, path=CLIENTS):
    c = json.load(open(path))
    if client not in c:
        raise SystemExit(f"няма клиент {client} в {path}")
    bank = (c[client].get("reviews") or {}).get("bank")
    if not bank:
        raise SystemExit(f"клиентът {client} няма reviews.bank в {path}")
    return os.path.expanduser(bank)


def find(pattern, text):
    m = re.search(pattern, text or "", re.I) if pattern else None
    return m.group(0) if m else None


def stats(reviews, lang="bg"):
    """reviews = списък от банката (вече филтриран по продукт). Връща речник с числата и групите."""
    p = PATTERNS.get(lang)
    if not p or not p["improve"]:
        raise SystemExit(f"няма изрази за език {lang} (PATTERNS в {__file__})")
    n = len(reviews)
    rated = [r for r in reviews if r.get("rating") is not None]
    five = sum(1 for r in rated if r["rating"] == 5)
    improve, fast, slow = [], [], []
    for r in reviews:
        body = r.get("body") or ""
        hit = find(p["improve"], body)
        if hit:
            improve.append(dict(name=r.get("name"), match=hit))
        hf = find(p["fast"], body)
        if hf:
            fast.append(dict(name=r.get("name"), match=hf))
            continue
        hs = find(p["slow"], body)
        if hs:
            slow.append(dict(name=r.get("name"), match=hs))
    timed = len(fast) + len(slow)
    pct = lambda a, b: round(100 * a / b) if b else 0
    return dict(n=n, rated=len(rated), five=five, five_pct=pct(five, len(rated)),
                improve=len(improve), improve_pct=pct(len(improve), n),
                fast=len(fast), slow=len(slow), timed=timed, fast_pct=pct(len(fast), timed),
                time_claim_ok=len(fast) >= MIN_FAST,
                groups=dict(improve=improve, fast=fast, slow=slow))


def ratio_words(a, n):
    """76% → „3/4“; по-грубо от процента, както в оригиналните блокове „4/5“."""
    if not n:
        return "0"
    best = min(((k, d) for d in (2, 3, 4, 5, 10) for k in range(1, d + 1)), key=lambda kd: abs(kd[0] / kd[1] - a / n))
    return f"{best[0]}/{best[1]}"


def ready_line(s):
    return (f"{s['five_pct']}% 5 звезди · {ratio_words(s['improve'], s['n'])} описват подобрение · "
            f"{s['fast_pct']}% ({s['fast']} от {s['timed']}) промяна в първата седмица")


def text_report(s, product):
    L = [f"Продукт: {product}", f"Отзиви: {s['n']} (с оценка {s['rated']})",
         f"5 звезди: {s['five']} = {s['five_pct']}%",
         f"Описват подобрение: {s['improve']} = {s['improve_pct']}%",
         f"Посочват срок: {s['timed']}; в първата седмица {s['fast']}, по-късно {s['slow']} → {s['fast_pct']}%", ""]
    for g, title in (("improve", "Подобрение"), ("fast", "Първата седмица"), ("slow", "По-късно")):
        L.append(f"## {title} ({len(s['groups'][g])})")
        L += [f"- {x['name']}: „{x['match']}“" for x in s["groups"][g]]
        L.append("")
    L.append("Готов ред: " + ready_line(s))
    if s["time_claim_ok"]:
        L.append(f"Срок („7 дни“): ДА, {s['fast']} отзива описват промяна в първата седмица (>= {MIN_FAST}).")
    else:
        L.append(f"Срок („7 дни“): НЕ, само {s['fast']} отзива за първата седмица (< {MIN_FAST}). Без срок в текста.")
    L.append("Бележка под числата: „*По отзивите на купувачите на сайта.“")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Числа за твърденията от банката с отзиви")
    ap.add_argument("--client", required=True)
    ap.add_argument("--product", required=True, help="handle на продукта в банката")
    ap.add_argument("--lang", default="bg")
    ap.add_argument("--bank", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    bank = os.path.expanduser(a.bank) if a.bank else client_bank(a.client)
    if not os.path.exists(bank):
        raise SystemExit(f"няма банка {bank}; построй я с review_bank.py")
    reviews = [r for r in json.load(open(bank)) if r.get("product") == a.product]
    if not reviews:
        raise SystemExit(f"няма отзиви за {a.product} в {bank}")
    s = stats(reviews, a.lang)
    if a.json:
        print(json.dumps(dict(s, product=a.product, line=ready_line(s)), ensure_ascii=False, indent=1))
    else:
        print(text_report(s, a.product))


if __name__ == "__main__":
    main()
