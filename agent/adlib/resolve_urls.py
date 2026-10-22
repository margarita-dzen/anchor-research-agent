"""Крайният адрес на всеки лендинг: следва пренасочванията и маха проследяващите параметри,
за да не се брои една и съща страница два пъти (bit.ly, l.facebook.com, ?utm_..., /pages/x/ срещу /pages/x).

    python3 agent/adlib/resolve_urls.py runs/example/ads_all.json [--out resolved.json] [--cache url_cache.json]
    python3 agent/evidence.py runs/example/ads_all.json --resolved runs/example/resolved.json

Ред: HEAD (по-евтино), при грешка или 4xx/5xx GET (+ <meta http-equiv="refresh">). Таймаут на заявка.
Кеш: url_cache.json до файла (по подразбиране 30 дни), --refresh тегли отново.
Изход resolved.json: {оригинален landing_url: чист краен URL}. Ако адресът не отговаря, остава
оригиналът без проследяващите параметри (пак е по-добре от суровия).
"""
import argparse, datetime, json, os, re, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
TRACKING_PREFIXES = ("utm_", "hsa_", "pk_", "mtm_", "fb_", "ga_", "_ga", "_gl", "mc_", "sc_", "tw_", "ttc_")
TRACKING = {"fbclid", "gclid", "gbraid", "wbraid", "dclid", "msclkid", "ttclid", "twclid", "li_fat_id", "igshid",
            "igsh", "si", "ref", "ref_src", "campaign_id", "adset_id", "ad_id", "ad_name", "adset_name",
            "campaign_name", "placement", "site_source_name", "h_ad_id", "_hsenc", "_hsmi", "mkt_tok", "irclickid",
            "srsltid", "epik", "_kx", "klaviyo_id", "cmp_id", "tw_source", "ad", "adid", "campaign", "source",
            "medium", "content", "fbc", "fbp", "external_id", "affiliate", "aff", "aff_id", "clickid", "click_id",
            "shpxid", "_pos", "_sid", "_ss", "_psq", "_fid"}
WRAPPERS = {"l.facebook.com": "u", "lm.facebook.com": "u", "l.instagram.com": "u", "l.messenger.com": "u"}
META_REFRESH = re.compile(rb'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?\s*\d+\s*;\s*url=([^"\'>\s]+)', re.I)


def is_tracking(key, value=""):
    k = key.lower()
    return k in TRACKING or k.startswith(TRACKING_PREFIXES) or "{{" in value


def clean_url(u):
    """https, без www., без фрагмент, без проследяващи параметри, подредени останали, без крайна /."""
    p = urlparse((u or "").strip())
    if not p.netloc:
        return ""
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    q = [(k, v) for k, vs in parse_qs(p.query, keep_blank_values=True).items() for v in vs if not is_tracking(k, v)]
    path = p.path.rstrip("/") or "/"
    return urlunparse(("https", host, path, "", urlencode(sorted(q)), ""))


def unwrap(u):
    """l.facebook.com/l.php?u=<истинският> → истинският."""
    p = urlparse(u)
    key = WRAPPERS.get(p.netloc.lower())
    if key:
        inner = parse_qs(p.query).get(key)
        if inner:
            return inner[0]
    return u


def http_fetch(url, method, timeout):
    """(статус, краен URL, първите 64 KB от тялото). urllib следва 301/302/303/307/308 сам."""
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        body = r.read(65536) if method == "GET" else b""
        return r.status, r.geturl(), body
    except urllib.error.HTTPError as e:
        return e.code, e.geturl() or url, b""


def resolve(url, fetch=http_fetch, timeout=10, max_refresh=3):
    """→ {final, clean, status, method, error}."""
    cur = unwrap(url)
    out = dict(final=cur, status=None, method=None, error=None)
    for _ in range(max_refresh + 1):
        try:
            status, final, body = fetch(cur, "HEAD", timeout)
            method = "HEAD"
            if status >= 400:
                status, final, body = fetch(cur, "GET", timeout)
                method = "GET"
        except Exception:
            try:
                status, final, body = fetch(cur, "GET", timeout)
                method = "GET"
            except Exception as e2:
                out["error"] = f"{type(e2).__name__}: {str(e2)[:120]}"
                break
        out.update(final=final, status=status, method=method, error=None)
        m = META_REFRESH.search(body or b"")
        if not m:
            break
        nxt = urljoin(final, m.group(1).decode("utf-8", "ignore"))
        if nxt == final:
            break
        cur = unwrap(nxt)
    out["clean"] = clean_url(out["final"]) or clean_url(url)
    return out


def resolve_all(urls, cache, fetch=http_fetch, timeout=10, workers=8, max_age_days=30, refresh=False, today=None):
    today = today or datetime.date.today()

    def fresh(u):
        c = cache.get(u)
        return c and not refresh and not c.get("error") and \
            (today - datetime.date.fromisoformat(c.get("checked", "1970-01-01"))).days <= max_age_days

    todo = [u for u in urls if u and not fresh(u)]

    def one(u):
        r = resolve(u, fetch, timeout)
        r["checked"] = str(today)
        return u, r

    with ThreadPoolExecutor(workers) as ex:
        for u, r in ex.map(one, todo):
            cache[u] = r
    return {u: (cache[u]["clean"] if u in cache else clean_url(u)) for u in urls if u}, len(todo)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ads", help="ads_all.json")
    ap.add_argument("--out", help="по подразбиране resolved.json до ads_all.json")
    ap.add_argument("--cache", help="по подразбиране url_cache.json до ads_all.json")
    ap.add_argument("--product", action="append")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-age", type=int, default=30, help="дни валидност на кеша")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.ads))
    out, cache_f = a.out or os.path.join(base, "resolved.json"), a.cache or os.path.join(base, "url_cache.json")
    ads = json.load(open(a.ads))
    urls = sorted({x.get("landing_url") for x in ads if x.get("landing_url")
                   and (not a.product or x.get("product") in a.product)})
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    mapping, fetched = resolve_all(urls, cache, timeout=a.timeout, workers=a.workers, max_age_days=a.max_age,
                                   refresh=a.refresh)
    json.dump(cache, open(cache_f, "w"), ensure_ascii=False, indent=1)
    json.dump(mapping, open(out, "w"), ensure_ascii=False, indent=1)
    errs = sum(1 for u in urls if cache.get(u, {}).get("error"))
    print(f"{len(urls)} URL-а · изтеглени {fetched} · грешки {errs} · {len(set(mapping.values()))} уникални крайни -> {out}")


if __name__ == "__main__":
    main()
