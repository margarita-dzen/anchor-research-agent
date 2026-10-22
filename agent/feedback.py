"""Одобренията и отказите от прегледите стават данни: какво поправя Валентин най-често.

    python3 agent/feedback.py ingest runs/<x> <папка с JSON от ArtifactData list --out_dir>   # добавя в runs/<x>/feedback.jsonl
    python3 agent/feedback.py report runs/*/                                               # честоти по категория → docs/learned-checks.md

Вход: документите от колекцията `reviews` в артефакта за преглед (doc id = ad:<код> / page:<handle> / flow:<стъпка>,
полета status approved|change, note, who, ts). Записва се само „change“ с бележка + броят одобрени.
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
        if d.get("status") != "change":
            continue
        c += 1
        rec = dict(run=os.path.basename(run.rstrip("/")), item=os.path.splitext(os.path.basename(f))[0], note=d.get("note", ""),
                   who=d.get("who"), ts=d.get("ts") or d.get("at"), cats=cats(d.get("note")))
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"прочетени {n}, промени {c} → {run}/feedback.jsonl")


def report(runs):
    rows = []
    for r in runs:
        p = os.path.join(r, "feedback.jsonl")
        if os.path.exists(p):
            rows += [json.loads(l) for l in open(p)]
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
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "learned-checks.md")
    open(path, "w").write("\n".join(lines))
    print("\n".join(lines[:12 + 4 * 3]))


if __name__ == "__main__":
    if sys.argv[1] == "ingest":
        ingest(sys.argv[2], sys.argv[3])
    else:
        report(sys.argv[2:])
