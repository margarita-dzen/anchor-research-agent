"""Сравнява две снимки на ads_all.json (едни и същи заявки, различни дати) по лендинг URL.

    python3 agent/adlib/snapshot_diff.py СТАР/ads_all.json НОВ/ads_all.json --out snapshot_diff.json \
        [--old-date 2026-10-20 --new-date 2026-11-03] [--resolved resolved.json] [--product acne]

Реклама = collation група (collation_id, иначе meta_ad_id). По URL:
  launched  нови в новата снимка с first_seen след старата дата (истински пуснати)
  seen_late нови в новата снимка, но пуснати преди старата дата (старото сваляне не ги е хванало)
  stopped   активни в старата, неактивни в новата
  missing   активни в старата, липсват в новата (спрени или извън обхвата на свалянето: по-слаб сигнал)
  running   активни и в двете
  net       launched - stopped - missing
Изходът е допълнителен сигнал за evidence: страница, която още пуска нови реклами, се скейлва.
"""
import argparse, collections, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from evidence import norm_url  # noqa: E402

KEYS = ("launched", "seen_late", "stopped", "missing", "running")


def ad_key(a):
    return a.get("collation_id") or a.get("meta_ad_id")


def latest_date(ads):
    ds = [a["first_seen"] for a in ads if a.get("first_seen")]
    return datetime.date.fromisoformat(max(ds)) if ds else None


def landing(a, resolved=None):
    resolved = resolved or {}
    u = resolved.get(a.get("landing_url")) or resolved.get(a.get("landing_url_clean")) or \
        a.get("landing_url_clean") or a.get("landing_url")
    return norm_url(u)


def diff(old, new, old_date, products=None, resolved=None, max_ids=20):
    keep = (lambda a: a.get("product") in products) if products else (lambda a: True)
    o = {ad_key(a): a for a in old if keep(a)}
    n = {ad_key(a): a for a in new if keep(a)}
    rows = collections.defaultdict(lambda: dict(brands=set(), **{k: [] for k in KEYS}))

    def put(kind, a):
        url, host = landing(a, resolved)
        r = rows[url]
        r["domain"] = host
        if a.get("brand"):
            r["brands"].add(a["brand"])
        r[kind].append(a.get("meta_ad_id"))

    for k, a in n.items():
        if k not in o:
            fs = a.get("first_seen")
            put("launched" if fs and datetime.date.fromisoformat(fs) > old_date else "seen_late", a)
        elif o[k].get("active") and a.get("active"):
            put("running", a)
        elif o[k].get("active"):
            put("stopped", a)
    for k, a in o.items():
        if k not in n and a.get("active"):
            put("missing", a)
    out = []
    for url, r in rows.items():
        row = dict(url=url, domain=r.get("domain", ""), brands=sorted(r["brands"]))
        for k in KEYS:
            row[k] = len(r[k])
        row["net"] = row["launched"] - row["stopped"] - row["missing"]
        row["ids"] = {k: r[k][:max_ids] for k in KEYS if r[k]}
        out.append(row)
    out.sort(key=lambda r: (-r["launched"], -r["running"], r["url"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--old-date", help="датата на старото сваляне (по подразбиране: най-новият first_seen в него)")
    ap.add_argument("--new-date")
    ap.add_argument("--product", action="append")
    ap.add_argument("--resolved", help="resolved.json от resolve_urls.py")
    ap.add_argument("--out")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()
    old, new = json.load(open(a.old)), json.load(open(a.new))
    od = datetime.date.fromisoformat(a.old_date) if a.old_date else latest_date(old)
    nd = datetime.date.fromisoformat(a.new_date) if a.new_date else latest_date(new)
    resolved = json.load(open(a.resolved)) if a.resolved else None
    rows = diff(old, new, od, set(a.product or []) or None, resolved)
    tot = {k: sum(r[k] for r in rows) for k in KEYS}
    if a.out:
        json.dump(dict(kind="snapshot-diff-v1", old=os.path.abspath(a.old), new=os.path.abspath(a.new),
                       old_date=str(od), new_date=str(nd), days=(nd - od).days if od and nd else None,
                       totals=tot, urls=rows), open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"{od} -> {nd} · " + " · ".join(f"{k} {v}" for k, v in tot.items()))
    print(f"{'нови':>5} {'късно':>5} {'спр':>4} {'липс':>4} {'върт':>4} {'нето':>5}  url")
    for r in rows[:a.top]:
        print(f"{r['launched']:5} {r['seen_late']:5} {r['stopped']:4} {r['missing']:4} {r['running']:4} {r['net']:5}  {r['url'][:80]}")


if __name__ == "__main__":
    main()
