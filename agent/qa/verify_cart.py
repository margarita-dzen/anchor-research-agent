"""Всеки бутон за купуване на клонинга стига ли до количката с правилните продукти? Само четене, нищо не се поръчва.

    python3 agent/qa/verify_cart.py --page <клонинг: URL или index.html> [--json out.json]
    python3 agent/qa/verify_cart.py --link "https://wearenordics.com/?anchor_cart=140558:1,140557:1"

1. Събира от страницата всички линкове към количката:
   - WooCommerce снипет #29 (Nordics): `?anchor_cart=ID:qty,ID:qty` (частите след qty, напр. цвят, се пазят в линка);
   - Shopify cart permalink: `/cart/<variant>:<qty>,...`.
2. Woo: всеки линк се отваря в НОВ анонимен headless контекст (сайтът има JS challenge за curl), пикселите са блокирани,
   после в същия контекст се чете `/wp-json/wc/store/v1/cart` и се сравнява: всеки очакван ID с бройката си.
   Пакет (bundle) идва като основен ред + компоненти: достатъчно е основният ID да е там.
3. Shopify: линковете минават през agent/playbooks/cart/verify_cart_paths.py --permalink (скриптът на Вальо
   от shopify-offer-funnel: анонимна количка, /cart.js, 422 = изчерпан компонент на пакет).
Изходен код 1, ако някой линк не пълни количката правилно. Поръчка не се прави, checkout не се попълва.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from urllib.parse import parse_qs, unquote, urljoin, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "..", "playbooks", "cart", "verify_cart_paths.py")
BLOCK = re.compile(r"facebook\.(net|com)|connect\.facebook|clarity\.ms|google-analytics|googletagmanager|doubleclick|tiktok|klaviyo|hotjar")
HREF = re.compile(r"""(?:href|data-href|data-link)\s*=\s*["']([^"']+)["']|["'](https?://[^"'\s]*anchor_cart=[^"'\s]+)["']""", re.I)


# ---------- чиста логика ----------

def parse_anchor_cart(url):
    """'?anchor_cart=140558:1,208899:1:color=pink' → [(140558, 1, 'color=pink'), (208899, 1, '')]"""
    q = parse_qs(urlparse(url).query).get("anchor_cart")
    if not q:
        return []
    out = []
    for part in unquote(q[0]).split(","):
        bits = part.strip().split(":")
        if not bits[0].isdigit():
            continue
        qty = int(bits[1]) if len(bits) > 1 and bits[1].isdigit() else 1
        out.append((int(bits[0]), qty, ":".join(bits[2:])))
    return out


def parse_shopify_permalink(url):
    m = re.search(r"/cart/((?:\d+:\d+,?)+)", urlparse(url).path)
    if not m:
        return []
    return [(int(v), int(q)) for v, q in (x.split(":") for x in m.group(1).strip(",").split(","))]


def cart_links(html, base=""):
    """Всички уникални линкове към количка в HTML (по реда на появата)."""
    seen, out = set(), []
    for m in HREF.finditer(html):
        u = (m.group(1) or m.group(2) or "").replace("&amp;", "&")
        if not u or u.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        u = urljoin(base, u) if base else u
        if ("anchor_cart=" in u or re.search(r"/cart/\d+:\d+", u)) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def compare_woo(expected, items):
    """expected [(id, qty, extra)], items от Store API → (ok, бележки)."""
    have = {}
    for it in items:
        for k in {it.get("id"), it.get("parent_id") if isinstance(it.get("parent_id"), int) else None} - {None}:
            have[k] = have.get(k, 0) + int(it.get("quantity") or 0)
    notes = []
    for pid, qty, extra in expected:
        if pid not in have:
            notes.append(f"{pid} липсва в количката")
        elif have[pid] < qty:
            notes.append(f"{pid}: в количката {have[pid]}, очаквани {qty}")
        if extra:
            attrs = " ".join(f"{a.get('attribute')}={a.get('value')}" for it in items if it.get("id") == pid for a in it.get("variation") or [])
            notes.append(f"{pid} [{extra}] → атрибути в количката: {attrs or 'няма'} (провери на ръка)")
    ok = not any("липсва" in n or "очаквани" in n for n in notes)
    return ok, notes


# ---------- браузър ----------

CLICKABLE = ".opt, .chip, .tier, .bundle, .pack, .swatch, .color, [data-variant], [data-id], [data-href], input[type=radio], label[for]"
JS_LINKS = """() => [...document.querySelectorAll('a[href], [data-href]')].map(e => e.href || e.dataset.href)
  .filter(u => u && (u.includes('anchor_cart=') || /\\/cart\\/\\d+:\\d+/.test(u)))"""


def collect_live(page_url, timeout=45000):
    """Линковете се сглобяват от JS (избор на пакет/цвят): щраква всяка опция и записва бутоните след всяко щракване."""
    from playwright.sync_api import sync_playwright
    url = page_url if re.match(r"https?://|file://", page_url) else "file://" + os.path.abspath(page_url)
    seen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # само headless
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.route("**/*", lambda r: r.abort() if BLOCK.search(r.request.url) else r.continue_())
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_timeout(1500)
        add = lambda: [seen.append(u) for u in page.evaluate(JS_LINKS) if u not in seen]
        add()
        els = page.query_selector_all(CLICKABLE)
        # опциите (пакети) × избора (цвят/животно): щраква всяка опция, после всеки избор в нея
        groups = {}
        for e in els:
            groups.setdefault(e.evaluate("e => e.className.split(' ')[0] || e.tagName"), []).append(e)
        keys = list(groups)
        for k in keys:
            for e in groups[k]:
                try:
                    e.evaluate("e => e.click()")
                    page.wait_for_timeout(80)
                    add()
                    for k2 in keys:
                        if k2 == k:
                            continue
                        for e2 in groups[k2]:
                            e2.evaluate("e => e.click()")
                            page.wait_for_timeout(40)
                            add()
                except Exception:  # noqa: BLE001
                    pass
        browser.close()
    return seen


def check_woo(links, timeout=45000):
    from playwright.sync_api import sync_playwright
    res = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # само headless
        for url in links:
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="bg-BG")
            ctx.route("**/*", lambda r: r.abort() if BLOCK.search(r.request.url) else r.continue_())
            page = ctx.new_page()
            row = dict(url=url, expected=[f"{a}:{b}" + (f":{c}" if c else "") for a, b, c in parse_anchor_cart(url)])
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_timeout(2500)
                row["landed"] = page.url
                origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                cart = page.evaluate("async (o) => { const r = await fetch(o + '/wp-json/wc/store/v1/cart', {credentials: 'include'}); return await r.json(); }", origin)
                items = cart.get("items") or []
                row["items"] = [dict(id=i.get("id"), qty=i.get("quantity"), name=i.get("name"),
                                     variation=[f"{a.get('attribute')}={a.get('value')}" for a in i.get("variation") or []]) for i in items]
                tot = cart.get("totals") or {}
                if tot.get("total_price") is not None:
                    row["total"] = int(tot["total_price"]) / 10 ** int(tot.get("currency_minor_unit", 2))
                row["ok"], row["notes"] = compare_woo(parse_anchor_cart(url), items)
            except Exception as e:  # noqa: BLE001
                row["ok"], row["notes"] = False, [f"грешка: {str(e)[:200]}"]
            res.append(row)
            ctx.close()
        browser.close()
    return res


def check_shopify(links):
    by_store = {}
    for u in links:
        p = urlparse(u)
        by_store.setdefault(f"{p.scheme}://{p.netloc}", []).append(u)
    res = []
    for store, us in by_store.items():
        cfg = dict(store=store, paths=[dict(name=u, lines=[dict(variant=v, qty=q) for v, q in parse_shopify_permalink(u)]) for u in us])
        with tempfile.TemporaryDirectory() as td:
            pj, rj = os.path.join(td, "paths.json"), os.path.join(td, "report.json")
            json.dump(cfg, open(pj, "w"))
            subprocess.run([sys.executable, "-I", VENDOR, pj, "--permalink", "--report", rj], capture_output=True, text=True, timeout=600)
            rep = json.load(open(rj)) if os.path.exists(rj) else []
        rows = rep if isinstance(rep, list) else rep.get("paths", [])
        for r in rows:
            res.append(dict(url=r.get("name"), ok=bool(r.get("ok")), notes=r.get("problems") or [], total=r.get("cart_total")))
        if not rows:
            res += [dict(url=u, ok=False, notes=["verify_cart_paths.py не върна отчет"]) for u in us]
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", help="клонинг: URL или локален HTML")
    ap.add_argument("--link", action="append", default=[], help="линк към количка (може няколко)")
    ap.add_argument("--list", action="store_true", help="само изброява линковете, без браузър")
    ap.add_argument("--json")
    a = ap.parse_args()
    links = list(a.link)
    if a.page:
        if os.path.exists(a.page):
            html = open(a.page, encoding="utf-8", errors="ignore").read()
            links += [u for u in cart_links(html) if u not in links]
        links += [u for u in collect_live(a.page) if u not in links]
    if not links:
        print("няма линкове към количка (anchor_cart или /cart/v:q)")
        sys.exit(1)
    woo = [u for u in links if "anchor_cart=" in u]
    shop = [u for u in links if u not in woo]
    print(f"линкове: {len(links)} (Woo {len(woo)}, Shopify {len(shop)})")
    if a.list:
        print("\n".join(links))
        return
    res = (check_woo(woo) if woo else []) + (check_shopify(shop) if shop else [])
    for r in res:
        print(f"{'OK ' if r['ok'] else 'ГРЕШКА'}  {r.get('total', '')!s:>7}  {r['url'][:110]}")
        for n in r.get("notes") or []:
            print("        ", n)
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    sys.exit(0 if all(r["ok"] for r in res) else 1)


if __name__ == "__main__":
    main()
