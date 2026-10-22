"""Сваля публичния Meta Ad Library (headless Chromium, без API ключ) за една заявка или една страница.

    python3 agent/adlib/scrape.py --q "eczema balm" --country GB --out raw/x.json [--scrolls 7]
    python3 agent/adlib/scrape.py --page-id 769145592941409 --country ALL --out raw/page.json

Подредбата е по импресии (най-показваните първи). Първите резултати са вградени в HTML-а като JSON,
следващите идват през graphql при скролване; четем и двете и вадим всеки обект с "ad_archive_id".
Изход: {"meta": {...}, "ads": [суровите обекти]}. Само headless: никога не отваря видим прозорец.
"""
import argparse, datetime, json, re, sys, time
from urllib.parse import quote

BASE = "https://www.facebook.com/ads/library/"


def library_url(q=None, page_id=None, country="ALL", active="active", sort="total_impressions"):
    """URL за търсене по ключова дума или за всички реклами на една страница (view_all_page_id)."""
    parts = [f"active_status={active}", "ad_type=all", f"country={country}", "media_type=all"]
    if page_id:
        parts += [f"view_all_page_id={page_id}", "search_type=page"]
    else:
        parts += [f"q={quote(q or '')}", "search_type=keyword_unordered"]
    if sort:
        parts += ["sort_data[direction]=desc", f"sort_data[mode]={sort}"]
    return BASE + "?" + "&".join(parts)


def _match_object(blob, start):
    """Индексът на затварящата скоба за JSON обекта, който започва на start (пропуска низове)."""
    depth, j, n = 0, start, len(blob)
    while j < n:
        c = blob[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        elif c == '"':
            j += 1
            while j < n and blob[j] != '"':
                if blob[j] == "\\":
                    j += 1
                j += 1
        j += 1
    return -1


def extract_ads(blobs):
    """Всички обекти с ad_archive_id от HTML/graphql текстове, без повторения (по ad_archive_id)."""
    ads = {}
    for blob in blobs:
        for m in re.finditer(r'"ad_archive_id":"(\d+)"', blob):
            start = blob.rfind('{"ad_archive_id"', 0, m.end())
            if start < 0:
                start = m.start() - 1
            end = _match_object(blob, start)
            if end < 0:
                continue
            try:
                o = json.loads(blob[start:end + 1])
            except ValueError:
                continue
            if isinstance(o, dict) and o.get("ad_archive_id"):
                ads[o["ad_archive_id"]] = o
    return list(ads.values())


def scrape(url, scrolls=7, wait=7.0, pause=2.5):
    """Отваря URL-а headless, скролва и връща (реклами, финален URL)."""
    from playwright.sync_api import sync_playwright
    captured = []

    def on_resp(r):
        if "api/graphql" in r.url:
            try:
                t = r.text()
                if "ad_archive_id" in t:
                    captured.append(t)
            except Exception:
                pass

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(locale="en-US", viewport={"width": 1400, "height": 1000})
        pg.on("response", on_resp)
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)

        def content():
            # FB понякога пренасочва по средата („page is navigating“): повтаряме
            for _ in range(10):
                try:
                    return pg.content()
                except Exception:
                    time.sleep(2)
            return ""

        time.sleep(wait)
        html0 = content()
        for _ in range(scrolls):
            try:
                pg.mouse.wheel(0, 6000)
            except Exception:
                pass
            time.sleep(pause)
        html = content()
        final = pg.url
        b.close()
    return extract_ads([html0, html] + captured), final


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--q", help="ключова дума")
    g.add_argument("--page-id", help="всички реклами на страница (view_all_page_id)")
    ap.add_argument("--country", default="ALL")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scrolls", type=int, default=7)
    ap.add_argument("--cat", default="", help="категория от run.json, записва се в meta")
    ap.add_argument("--active", default="active", help="active или all")
    a = ap.parse_args()
    url = library_url(a.q, a.page_id, a.country, a.active)
    ads, final = scrape(url, a.scrolls)
    meta = dict(cat=a.cat or ("page" if a.page_id else ""), country=a.country, q=a.q, page_id=a.page_id,
                mode="page" if a.page_id else "keyword", url=url, scraped_at=str(datetime.date.today()))
    json.dump(dict(meta=meta, ads=ads), open(a.out, "w"), ensure_ascii=False)
    print("final url:", final[:100], file=sys.stderr)
    print(len(ads), "ads ->", a.out)


if __name__ == "__main__":
    main()
