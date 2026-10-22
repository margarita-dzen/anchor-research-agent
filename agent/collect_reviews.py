"""Сваля всички истински отзиви (текст + снимки + видео) от Judge.me за Shopify магазин.

    python3 agent/collect_reviews.py --site https://sosimplecosmetics.eu \
        --shop so-simple-cosmetics.myshopify.com --out ~/Clients/So-Simple/reviews

Изход: <out>/reviews.json (всички отзиви по продукт, дословно, с име и дата),
       <out>/photos/<handle>/<uuid>_<n>.jpg (снимките от отзивите), <out>/summary.json.
Публичният widget endpoint на Judge.me не иска ключ. Само четене.
"""
import argparse, html, json, os, re, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (anchor-research-agent)"}


def get_json(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def products(site):
    out, page = [], 1
    while True:
        batch = get_json(f"{site}/products.json?limit=250&page={page}")["products"]
        if not batch:
            return out
        out += [dict(id=p["id"], handle=p["handle"], title=p["title"]) for p in batch]
        page += 1


def reviews_for(shop, pid):
    rows, page = [], 1
    while True:
        d = get_json(f"https://judge.me/reviews/reviews_for_widget?url={shop}&shop_domain={shop}"
                     f"&platform=shopify&page={page}&per_page=50&product_id={pid}")
        rows += d.get("reviews") or []
        if page >= ((d.get("pagination") or {}).get("total_pages") or 1):
            return rows, d.get("number_of_reviews", 0), d.get("average_rating")
        page += 1
        time.sleep(0.3)


def text(body_html):
    t = re.sub(r"<br\s*/?>|</p>", "\n", body_html or "")
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def download(url, path):
    if os.path.exists(path):
        return True
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            open(path, "wb").write(r.read())
        return True
    except Exception:
        return False


def woo(site, out):
    """WooCommerce Store API (публичен): /wp-json/wc/store/v1/products/reviews. Снимки към отзивите API-то не дава."""
    allr, page = [], 1
    while True:
        batch = get_json(f"{site}/wp-json/wc/store/v1/products/reviews?per_page=100&page={page}")
        if not batch:
            break
        for r in batch:
            allr.append(dict(product=r["product_permalink"].rstrip("/").rsplit("/", 1)[-1], product_title=r["product_name"],
                             uuid=str(r["id"]), name=r.get("reviewer"), anonymous=False, rating=r.get("rating"), title="",
                             body=text(r.get("review")), date=(r.get("date_created") or "")[:10], language=None,
                             verified=r.get("verified"), location=None, pictures=[], videos=[], variant=None, from_bundle=None))
        page += 1
    json.dump(allr, open(f"{out}/reviews.json", "w"), ensure_ascii=False, indent=1)
    by = {}
    for r in allr:
        by.setdefault(r["product"], dict(handle=r["product"], title=r["product_title"], reviews=0, with_media=0))["reviews"] += 1
    json.dump(sorted(by.values(), key=lambda s: -s["reviews"]), open(f"{out}/summary.json", "w"), ensure_ascii=False, indent=1)
    print(f"общо {len(allr)} отзива, {len(by)} продукта")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True)
    ap.add_argument("--shop", help="*.myshopify.com домейнът (Shopify + Judge.me)")
    ap.add_argument("--platform", choices=["shopify", "woo"], default="shopify")
    ap.add_argument("--out", required=True)
    ap.add_argument("--handle", action="append", help="само тези продукти")
    a = ap.parse_args()
    out = os.path.expanduser(a.out)
    os.makedirs(f"{out}/photos", exist_ok=True)
    if a.platform == "woo":
        return woo(a.site.rstrip("/"), out)
    prods = [p for p in products(a.site.rstrip("/")) if not a.handle or p["handle"] in a.handle]
    allr, summary = [], []
    for p in prods:
        rs, total, avg = reviews_for(a.shop, p["id"])
        n_media = 0
        for r in rs:
            pics = []
            for i, pu in enumerate(r.get("pictures_urls") or []):
                url = pu.get("original") or pu.get("huge")
                os.makedirs(f"{out}/photos/{p['handle']}", exist_ok=True)
                local = f"photos/{p['handle']}/{r['uuid']}_{i}.jpg"
                pics.append(dict(url=url, local=local if download(url, f"{out}/{local}") else None))
            vids = list(r.get("video_external_ids") or []) + [v.get("url") or v for v in (r.get("media_platform_hosted_video_infos") or [])]
            n_media += bool(pics or vids)
            allr.append(dict(product=p["handle"], product_title=p["title"], uuid=r["uuid"], name=r.get("reviewer_name"),
                             anonymous=r.get("is_anonymous_reviewer"), rating=r.get("rating"), title=r.get("title"),
                             body=text(r.get("body_html")), date=(r.get("created_at") or "")[:10], language=r.get("language"),
                             verified=r.get("verified_buyer"), location=r.get("location"), pictures=pics, videos=vids,
                             variant=r.get("product_variant_title"), from_bundle=r.get("is_for_product_from_bundle")))
        summary.append(dict(handle=p["handle"], title=p["title"], reviews=len(rs), reported=total, avg=avg, with_media=n_media))
        print(f"{len(rs):4} отзива, {n_media:3} със снимка/видео  {p['handle']}", flush=True)
    json.dump(allr, open(f"{out}/reviews.json", "w"), ensure_ascii=False, indent=1)
    summary.sort(key=lambda s: -s["with_media"])
    json.dump(summary, open(f"{out}/summary.json", "w"), ensure_ascii=False, indent=1)
    print(f"общо {len(allr)} отзива, {sum(s['with_media'] for s in summary)} със снимка/видео, {len(prods)} продукта")


if __name__ == "__main__":
    main()
