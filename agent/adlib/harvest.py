"""Пуска заявките от run.json (или пълно сваляне по страница) през scrape.py, по 2 паралелно.

    python3 agent/adlib/harvest.py runs/example/run.json [--limit 1] [--scrolls 2] [--cat acne] [--country DE]
    python3 agent/adlib/harvest.py runs/example/run.json --pages 769145592941409,104725111411722
    python3 agent/adlib/harvest.py runs/example/run.json --top-pages 5 [--product acne]

Файлове: <output_dir>/raw/<cat>__<CC>__<заявка>.json и raw/page__<CC>__<page_id>.json.
Вече свалени файлове с реклами се пропускат. Файл с 0 реклами (FB е пренасочил) се трие и заявката
се пуска отново (до scrape.retries кръга). --top-pages взима най-силните рекламодатели от ads_all.json
(активни реклами + дубликати), затова първо пусни consolidate.py.
"""
import argparse, collections, datetime, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runconfig  # noqa: E402


def count_ads(f):
    try:
        d = json.load(open(f))
    except (OSError, ValueError):
        return -1
    return len(d["ads"] if isinstance(d, dict) else d)


def keyword_jobs(cfg, limit=None, cat=None, scrolls=None, country=None):
    jobs = []
    for q in cfg["queries"]:
        if cat and q["cat"] != cat or country and q["country"] != country:
            continue
        f = runconfig.path(cfg, "raw", runconfig.raw_name(q["cat"], q["country"], q["q"]))
        jobs.append(dict(args=["--q", q["q"], "--country", q["country"], "--cat", q["cat"]], out=f,
                         scrolls=scrolls or cfg["scrape"]["scrolls"], label=f"{q['country']} {q['q']}"))
    return jobs[:limit] if limit else jobs


def page_jobs(cfg, page_ids, country=None, scrolls=None):
    pc = cfg["pages"]
    cc = country or pc["country"]
    return [dict(args=["--page-id", str(pid), "--country", cc, "--cat", "page"],
                 out=runconfig.path(cfg, "raw", runconfig.raw_name("page", cc, page_id=pid)),
                 scrolls=scrolls or pc["scrolls"], label=f"page {pid} ({cc})") for pid in page_ids]


def top_pages(ads, n, products=None, skip=()):
    """Най-силните рекламодатели: брой активни реклами + сбор дубликати на активните."""
    score, names = collections.Counter(), {}
    for a in ads:
        if not a.get("page_id") or not a.get("active") or str(a["page_id"]) in skip:
            continue
        if products and a.get("product") not in products:
            continue
        score[str(a["page_id"])] += 1 + (a.get("duplicates") or 1)
        names[str(a["page_id"])] = a.get("brand")
    return [(pid, names[pid], s) for pid, s in score.most_common(n)]


def run_job(j, active):
    cmd = [sys.executable, os.path.join(HERE, "scrape.py"), *j["args"], "--out", j["out"],
           "--scrolls", str(j["scrolls"]), "--active", active]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=400)
        tail = (r.stdout or r.stderr).strip().splitlines()
        return f"{j['label']}: {tail[-1] if tail else 'няма изход'}"
    except subprocess.TimeoutExpired:
        return f"{j['label']}: timeout"


def harvest(cfg, jobs):
    os.makedirs(runconfig.path(cfg, "raw"), exist_ok=True)
    sc = cfg["scrape"]
    for rnd in range(1 + int(sc["retries"])):
        todo = []
        for j in jobs:
            n = count_ads(j["out"])
            if n == 0:
                os.remove(j["out"])  # 0 реклами = пренасочване, не истински празен резултат
            if n <= 0:
                todo.append(j)
        if not todo:
            break
        if rnd:
            print(f"-- повторен кръг {rnd}: {len(todo)} заявки с 0 реклами", flush=True)
            time.sleep(20)
        with ThreadPoolExecutor(sc["parallel"]) as ex:
            for s in ex.map(lambda j: run_job(j, sc["active"]), todo):
                print(s, flush=True)
    empty = [j["label"] for j in jobs if count_ads(j["out"]) <= 0]
    meta = runconfig.path(cfg, "raw", "_meta.json")
    m = json.load(open(meta)) if os.path.exists(meta) else {}
    m["scrape_date"] = str(datetime.date.today())
    json.dump(m, open(meta, "w"), indent=1)
    print(f"готово: {len(jobs) - len(empty)}/{len(jobs)} с реклами" + (f"; без реклами: {empty}" if empty else ""))
    return empty


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--limit", type=int, help="само първите N заявки (за проба)")
    ap.add_argument("--cat", help="само заявки от тази категория")
    ap.add_argument("--scrolls", type=int)
    ap.add_argument("--pages", help="page_id-та през запетая (или config = pages.ids): всички реклами на страницата")
    ap.add_argument("--top-pages", type=int, help="топ N рекламодатели от ads_all.json")
    ap.add_argument("--product", action="append", help="за --top-pages: само рекламодатели с този product")
    ap.add_argument("--country", help="само заявки за тази държава; за --pages/--top-pages: държавата (по подразбиране pages.country)")
    a = ap.parse_args()
    cfg = runconfig.load(a.run)
    if a.pages or a.top_pages:
        ids = [str(p) for p in cfg["pages"]["ids"]] if a.pages == "config" else \
            [p.strip() for p in (a.pages or "").split(",") if p.strip()]
        if a.top_pages:
            ads = json.load(open(runconfig.path(cfg, "ads_all.json")))
            top = top_pages(ads, a.top_pages, set(a.product or cfg["pages"]["products"] or []) or None, set(ids))
            for pid, name, s in top:
                print(f"  {pid}  {name}  ({s})")
            ids += [pid for pid, _, _ in top]
        jobs = page_jobs(cfg, ids, a.country, a.scrolls)
    else:
        jobs = keyword_jobs(cfg, a.limit, a.cat, a.scrolls, a.country)
    print(f"{len(jobs)} заявки, по {cfg['scrape']['parallel']} паралелно", flush=True)
    harvest(cfg, jobs)


if __name__ == "__main__":
    main()
