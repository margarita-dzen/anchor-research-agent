"""Одобренията и отказите от прегледите стават данни: какво поправя Валентин най-често.

    python3 agent/feedback.py ingest runs/<x> <папка с JSON от ArtifactData list --out_dir>   # добавя в runs/<x>/feedback.jsonl
    python3 agent/feedback.py ingest-md runs/<x> <бележки.md> [--item page:<папка>]          # поправки, дадени в чата (номериран списък)
    python3 agent/feedback.py report runs/*/                                               # честоти по категория → docs/learned-checks.md

Вход: документите от колекцията `reviews` в артефакта за преглед (doc id = ad:<код> / page:<handle> / flow:<стъпка>,
полета status approved|change, note, who, ts). Записва се „change“ с бележка, а отговорите на въпроси (doc id q-*, без status, с бележка) като kind=answer:
те са решения на Валентин и отиват в отделна секция „Решения“ на learned-checks.md.
Категориите са по ключови думи в бележката. Нова повтаряща се грешка → добави категория тук и проверка в agent/qa/.
"""
import collections, glob, json, os, re, sys

CATS = {
    "не е като оригинала": r"оригинал|пример|като при тях|1:1|клонир|различ",
    "снимка / визия": r"снимк|визи|картин|кадър|фон|дете|бебе|ръц|лице|генерир|снимката",
    "продукт във визията": r"стик|опаковк|размер на стика|твърде голям|твърде малък|пакшот",
    "текст / копи": r"текст|копи|заглави|хедлайн|дум|изречени|правопис|грешк|превод",
    "оферта / цена": r"оферт|цена|пакет|подар|отстъпк|2\+1|безплатн|доставк",
    "забранено / правило": r"илюстратив|рекламна публикация|звездичк|дисклеймър|лекува|100%|гаранц|тире|—",
    "отзиви": r"отзив|ревю|клиент|име|цитат|проверен купувач",
    "дизайн / шрифт / цвят": r"шрифт|цвят|цвет|бутон|дизайн|разстояни|подравн|болд|сем?пл",
    "мобилно / техническо": r"мобил|390|телефон|скрол|не зарежда|бавн|счупен|линк",
    "бутон / CTA / количка": r"бутон|CTA|главни букви|залепен|sticky|количк|снипет|anchor_cart|наличност и специални",
    "UGC / деца": r"UGC|ло-фи|баня|дете|деца|детск|карусел",
    "наличност / доставка / твърдения": r"наличност|ограничен|голямо търсене|доставк|№1|номер 1|гаранц|продадени",
    "излишно / липсващо": r"без секция|махни|няма повторен|излишн|празни|кръстосан",
}


def cats(note):
    return [c for c, p in CATS.items() if re.search(p, note or "", re.I)] or ["друго"]


def ingest(run, folder):
    out = open(os.path.join(run, "feedback.jsonl"), "a")
    n = c = 0
    for f in glob.glob(os.path.join(folder, "**", "*.json"), recursive=True):
        d = json.load(open(f))
        d = d.get("data", d)
        n += 1
        item = os.path.splitext(os.path.basename(f))[0]
        answer = item.startswith("q-") and not d.get("status") and (d.get("note") or "").strip()
        if d.get("status") != "change" and not answer:
            continue
        c += 1
        rec = dict(run=os.path.basename(run.rstrip("/")), item=item, note=(d.get("note") or "").strip(),
                   who=d.get("who"), ts=d.get("ts") or d.get("at"), cats=cats(d.get("note")), kind="answer" if answer else "change")
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"прочетени {n}, промени {c} → {run}/feedback.jsonl")


def parse_md(text):
    """Номериран или булет списък → бележки. Подточките (отстъп) се лепят към горната точка."""
    notes, skip = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            skip = bool(re.search(r"Проверка|Изход|Върни|Задължително четене", line))  # инструкции, не поправки
            continue
        if skip and not re.match(r"^\d+\.", line):
            continue
        m = re.match(r"^(\s*)(?:\d+\.|[-*])\s+(.*\S)", line)
        if not m:
            continue
        if m.group(1) and notes:
            notes[-1] += "; " + m.group(2)
        else:
            notes.append(m.group(2))
    return notes


def ingest_md(run, path, item=None):
    notes = parse_md(open(path).read())
    item = item or "md:" + os.path.basename(path)
    with open(os.path.join(run, "feedback.jsonl"), "a") as out:
        for nt in notes:
            out.write(json.dumps(dict(run=os.path.basename(run.rstrip("/")), item=item, note=nt, who="Валентин", ts=None,
                                      cats=cats(nt), kind="change"), ensure_ascii=False) + "\n")
    print(f"{len(notes)} бележки от {path} → {run}/feedback.jsonl")


def report(runs):
    rows = []
    for r in runs:
        p = os.path.join(r, "feedback.jsonl")
        if os.path.exists(p):
            rows += [json.loads(l) for l in open(p)]
    answers = [r for r in rows if r.get("kind") == "answer"]
    rows = [r for r in rows if r.get("kind") != "answer"]
    cnt = collections.Counter(c for r in rows for c in r["cats"])
    ex = collections.defaultdict(list)
    for r in rows:
        for c in r["cats"]:
            if len(ex[c]) < 3:
                ex[c].append(f"{r['run']} / {r['item']}: {r['note'][:120]}")
    lines = ["# Научени проверки (от прегледите)", "", f"Общо {len(rows)} поискани промени.", "",
             "Най-честите категории се проверяват ПРЕДИ да се покаже нещо за преглед.", ""]
    for c, n in cnt.most_common():
        lines.append(f"## {c} ({n})")
        lines += [f"- {e}" for e in ex[c]]
        lines.append("")
    if answers:
        lines += ["## Решения (отговори на въпроси в прегледа)", ""]
        lines += [f"- {r['run']} / {r['item']}: {r['note'][:200]}" for r in answers]
        lines.append("")
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "learned-checks.md")
    open(path, "w").write("\n".join(lines))
    print("\n".join(lines[:12 + 4 * 3]))


if __name__ == "__main__":
    if sys.argv[1] == "ingest":
        ingest(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "ingest-md":
        ingest_md(sys.argv[2], sys.argv[3], sys.argv[sys.argv.index("--item") + 1] if "--item" in sys.argv else None)
    else:
        report(sys.argv[2:])
