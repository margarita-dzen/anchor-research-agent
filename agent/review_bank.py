"""Обединява всички истински отзиви на клиента в една банка по продукт.

    python3 agent/review_bank.py ~/Clients/So-Simple/reviews

Чете от папката:
  reviews.json                 (collect_reviews.py, Judge.me на живо)
  drive/**/*.csv               (износ от Judge.me: title, body, rating, review_date, reviewer_name, product_handle, picture_urls)
  drive/**/*.xlsx              (таблици „Име | Отзив“, напр. препоръки от Facebook; продуктът = името на файла)
Пише bank.json и bank.md. Имейлите и IP адресите от износите НЕ се копират.
Дубликатите (същото име + същото начало на текста) се сливат, а снимките се запазват.
"""
import csv, glob, json, os, re, sys


def key(name, body):
    n = re.sub(r"\W+", "", (name or "").lower())
    b = re.sub(r"\W+", "", (body or "").lower())[:60]
    return n + "|" + b


def clean_name(n):
    n = re.sub(r"\s*препоръчва\s+So Simple.*$", "", (n or "").replace("\xa0", " ")).strip()
    return n


def load(root):
    rows = []
    p = os.path.join(root, "reviews.json")
    if os.path.exists(p):
        for r in json.load(open(p)):
            rows.append(dict(product=r["product"], name=r["name"], body=r["body"], rating=r["rating"], date=r["date"],
                             language=r.get("language"), pictures=[x["local"] or x["url"] for x in r["pictures"]],
                             videos=r["videos"], source="judge.me"))
    for f in glob.glob(os.path.join(root, "drive", "**", "*.csv"), recursive=True):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            if not r.get("body"):
                continue
            pics = [u for u in re.split(r"[,\s]+", r.get("picture_urls") or "") if u.startswith("http")]
            rows.append(dict(product=r.get("product_handle"), name=r.get("reviewer_name"), body=r["body"],
                             rating=int(float(r.get("rating") or 5)), date=(r.get("review_date") or "")[:10],
                             language=None, pictures=pics, videos=[], source=f"drive csv: {os.path.basename(f)}"))
    try:
        import openpyxl
    except ImportError:
        openpyxl = None
    for f in glob.glob(os.path.join(root, "drive", "**", "*.xlsx"), recursive=True):
        if not openpyxl:
            print("openpyxl липсва, пропускам", f)
            continue
        ws = openpyxl.load_workbook(f, read_only=True).active
        it = ws.iter_rows(values_only=True)
        head = [str(h or "").strip().lower() for h in next(it, [])]
        if "отзив" not in head:
            continue
        ni, bi = head.index("име") if "име" in head else 0, head.index("отзив")
        for r in it:
            if not r or not r[bi]:
                continue
            rows.append(dict(product="xlsx:" + os.path.splitext(os.path.basename(f))[0], name=clean_name(str(r[ni] or "")),
                             body=str(r[bi]).replace("\xa0", " ").strip(), rating=None, date=None, language=None,
                             pictures=[], videos=[], source=f"drive xlsx: {os.path.basename(f)}"))
    return rows


def merge(rows):
    bank = {}
    for r in rows:
        k = key(r["name"], r["body"])
        if k in bank:
            b = bank[k]
            b["pictures"] = list(dict.fromkeys(b["pictures"] + r["pictures"]))
            b["videos"] = list(dict.fromkeys(b["videos"] + r["videos"]))
            b["sources"] = sorted(set(b["sources"]) | {r["source"]})
            if b["product"].startswith("xlsx:") and not r["product"].startswith("xlsx:"):
                b["product"] = r["product"]
        else:
            bank[k] = dict(r, sources=[r.pop("source")])
            bank[k].pop("source", None)
    return list(bank.values())


def main():
    root = os.path.expanduser(sys.argv[1])
    bank = merge(load(root))
    bank.sort(key=lambda r: (r["product"] or "", -len(r["pictures"]) - len(r["videos"]), r["date"] or ""))
    json.dump(bank, open(os.path.join(root, "bank.json"), "w"), ensure_ascii=False, indent=1)
    by = {}
    for r in bank:
        s = by.setdefault(r["product"] or "?", dict(total=0, media=0))
        s["total"] += 1
        s["media"] += bool(r["pictures"] or r["videos"])
    lines = ["# Банка с отзиви", "", f"Общо {len(bank)} уникални отзива, {sum(s['media'] for s in by.values())} със снимка/видео.", "",
             "| Продукт | Отзиви | Със снимка/видео |", "|---|---|---|"]
    lines += [f"| {p} | {s['total']} | {s['media']} |" for p, s in sorted(by.items(), key=lambda x: (-x[1]["media"], -x[1]["total"]))]
    lines += ["", "## Всички отзиви със снимка/видео", ""]
    for r in bank:
        if r["pictures"] or r["videos"]:
            lines.append(f"- **{r['product']}** · {r['name']} · {r['date'] or ''} · {len(r['pictures'])} снимки, {len(r['videos'])} видео · {r['body'][:140].replace(chr(10), ' ')}")
    open(os.path.join(root, "bank.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:4 + 2 + len(by)]))


if __name__ == "__main__":
    main()
