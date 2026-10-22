"""EU обхват (eu_total_reach) за най-силните кандидати: прозрачността по DSA, която Ad Library показва
в „See ad details“ за реклами, пускани в ЕС.

    python3 agent/adlib/eu_reach.py runs/example/run.json [--top 100] [--product acne]

Защо отделно: търсенето (scrape.py) връща reach_estimate = null за всяка реклама (проверено върху 4 715
сурови реклами на So Simple), обхватът идва само от заявката AdLibraryV3AdDetailsQuery.
Как: една headless сесия отваря ?id=<реклама> и натиска „See ad details“, за да хване истинската заявка
(doc_id и токените се сменят, затова не са в кода). После същата заявка се праща с fetch от страницата за
всеки кандидат, ~0,6 с на реклама. Кеш: <output_dir>/eu_reach_cache.json (повторно пускане не тегли отново).
В ads_all.json: eu_reach (хора в ЕС, за целия живот на рекламата; null = не е пускана в ЕС)
и eu_reach_countries (държави по обхват).
"""
import argparse, datetime, json, os, sys, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runconfig  # noqa: E402
from thumbs import score  # noqa: E402

DETAILS = "AdLibraryV3AdDetailsQuery"
FETCH_JS = """async (b) => {
  const r = await fetch('/api/graphql/', {method: 'POST', body: b, credentials: 'include',
    headers: {'content-type': 'application/x-www-form-urlencoded'}});
  return await r.text(); }"""


def parse_details(text):
    """Отговор на AdLibraryV3AdDetailsQuery → {eu_reach, targets_eu, countries, reach_by_country, gender, age}.
    None, ако отговорът не е разпознат (грешка, лимит)."""
    d = None
    for line in (text or "").splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if isinstance(o, dict) and (o.get("data") or {}).get("ad_library_main"):
            d = o
            break
    if d is None:
        return None
    det = d["data"]["ad_library_main"].get("ad_details") or {}
    eu = (det.get("transparency_by_location") or {}).get("eu_transparency") or {}
    by_cc = {}
    for c in eu.get("age_country_gender_reach_breakdown") or []:
        n = 0
        for b in c.get("age_gender_breakdowns") or []:
            n += sum(v or 0 for k, v in b.items() if k in ("male", "female", "unknown"))
        by_cc[c.get("country")] = n
    age = eu.get("age_audience") or {}
    return dict(eu_reach=eu.get("eu_total_reach"), targets_eu=bool(eu.get("targets_eu")),
                countries=sorted(by_cc, key=lambda k: -by_cc[k]), reach_by_country=by_cc,
                gender=eu.get("gender_audience"), age=[age.get("min"), age.get("max")] if age else None)


def candidates(ads, top, products=None, cached=()):
    pool = [a for a in ads if a.get("active") and a["meta_ad_id"] not in cached
            and (not products or a.get("product") in products)]
    return sorted(pool, key=lambda a: -score(a))[:top]


class DetailsSession:
    """Една headless сесия: хваща шаблона на заявката от първия клик и после праща fetch за всяка реклама."""

    def __init__(self, page):
        self.pg, self.tmpl = page, None
        page.on("request", self._on_req)

    def _on_req(self, r):
        if "api/graphql" in r.url and DETAILS in (r.post_data or ""):
            self.tmpl = urllib.parse.parse_qs(r.post_data, keep_blank_values=True)

    def prime(self, ad):
        self.pg.goto(f"https://www.facebook.com/ads/library/?id={ad['meta_ad_id']}", wait_until="domcontentloaded",
                     timeout=60000)
        time.sleep(6)
        for label in ("See ad details", "See summary details"):
            loc = self.pg.get_by_text(label)
            if loc.count():
                loc.first.click()
                for _ in range(10):
                    if self.tmpl:
                        return True
                    time.sleep(1)
        return bool(self.tmpl)

    def fetch(self, ad):
        q = {k: v[0] for k, v in self.tmpl.items()}
        v = json.loads(q["variables"])
        v.update(adArchiveID=str(ad["meta_ad_id"]), pageID=str(ad.get("page_id") or ""))
        q["variables"] = json.dumps(v)
        return self.pg.evaluate(FETCH_JS, urllib.parse.urlencode(q))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--top", type=int)
    ap.add_argument("--product", action="append")
    a = ap.parse_args()
    cfg = runconfig.load(a.run)
    ec = cfg["eu_reach"]
    src, cache_f = runconfig.path(cfg, "ads_all.json"), runconfig.path(cfg, "eu_reach_cache.json")
    ads = json.load(open(src))
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    todo = candidates(ads, a.top or ec["top"], set(a.product or ec["products"] or []) or None, set(cache))
    print(f"{len(todo)} кандидата (кеш: {len(cache)})", flush=True)
    if todo:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            s = DetailsSession(b.new_page(locale="en-US", viewport={"width": 1400, "height": 1000}))
            if not any(s.prime(x) for x in todo[:3]):
                b.close()
                sys.exit("не хванах AdLibraryV3AdDetailsQuery (бутонът „See ad details“ липсва?)")
            errors = 0
            for i, x in enumerate(todo):
                r = None
                for attempt in range(2):
                    try:
                        r = parse_details(s.fetch(x))
                    except Exception:
                        r = None
                    if r is not None:
                        break
                    time.sleep(5)
                if r is None:
                    errors += 1
                    if errors >= 5:
                        print("5 поредни грешки: спирам (лимит от FB?)")
                        break
                    continue
                errors = 0
                r["fetched"] = str(datetime.date.today())
                cache[x["meta_ad_id"]] = r
                if i % 20 == 0:
                    json.dump(cache, open(cache_f, "w"), ensure_ascii=False)
                time.sleep(0.3)
            b.close()
        json.dump(cache, open(cache_f, "w"), ensure_ascii=False)
    n = 0
    for x in ads:
        c = cache.get(x["meta_ad_id"])
        if c:
            x["eu_reach"], x["eu_reach_countries"] = c.get("eu_reach"), c.get("countries") or []
            n += 1
    json.dump(ads, open(src, "w"), ensure_ascii=False, indent=1)
    top = sorted((x for x in ads if x.get("eu_reach")), key=lambda x: -x["eu_reach"])[:10]
    print(f"{n} реклами с данни; с EU обхват: {sum(1 for x in ads if x.get('eu_reach'))}")
    for x in top:
        print(f"{x['eu_reach']:>10,}  {','.join(x['eu_reach_countries'][:4]):<12} {x['brand'][:30]:<30} {x['landing_url_clean'][:60]}")


if __name__ == "__main__":
    main()
