#!/usr/bin/env python3
"""Prove every funnel path actually lands in the store's cart with the right lines and price.

For each path in an offer-paths JSON (see templates/offer-paths.example.json) this opens a
FRESH anonymous session on the store (new cookie jar, like a new visitor) and:

  1. POST /cart/add.js with the path's variant lines            -> 200 ok, or 422 (sold out,
                                                                   unpublished, bad variant)
  2. POST /cart/update.js with the path's cart attributes        (only if the path has any)
  3. GET  /cart.js                                               -> compares lines, quantities,
                                                                   total and attributes

On a 422 it retries line by line so the report names the exact variant that fails. A bundle
product whose component is sold out returns 422 "already sold out" even when the main product
looks in stock on the product page: this is the check that catches it.

--permalink mode tests the real handoff link instead: it requests
  /cart/<variant>:<qty>,...?ref=..&attributes[k]=v
in a fresh session WITHOUT following the redirect to checkout, then reads /cart.js.

Safety: anonymous carts only. Nothing is bought, no checkout is completed, no order is
created, no key is needed. It does create throwaway cart sessions on the store, which is
what a normal visitor does. Use --print-links to only print the permalinks (no network).

Examples
  python3 verify_cart_paths.py paths.json
  python3 verify_cart_paths.py paths.json --permalink
  python3 verify_cart_paths.py paths.json --only "flood" --report report.json
  python3 verify_cart_paths.py paths.json --print-links
"""
import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # stop at the first redirect; cookies from that response are already stored


def session(follow=True):
    jar = http.cookiejar.CookieJar()
    handlers = [urllib.request.HTTPCookieProcessor(jar)]
    if not follow:
        handlers.append(NoRedirect())
    op = urllib.request.build_opener(*handlers)
    op.addheaders = [('User-Agent', UA), ('Accept', 'application/json')]
    return op


def call(op, url, body=None, retries=3):
    """Returns (status, parsed body). Backs off on 429 (rate limit or the store's bot check)."""
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'} if data else {})
        try:
            with op.open(req, timeout=30) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw[:1] in (b'{', b'[') else raw.decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code == 429 and attempt < retries:
                time.sleep(10 * (attempt + 1))
                continue
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw.decode('utf-8', 'replace')


def base_url(cfg, path):
    store = (path.get('store') or cfg['store']).rstrip('/')
    loc = path.get('locale', cfg.get('locale', ''))
    return store + (f'/{loc}' if loc else '')


def permalink(cfg, path):
    lines = ','.join(f"{l['variant']}:{l.get('qty', 1)}" for l in path['lines'])
    q = []
    ref = path.get('ref', cfg.get('ref'))
    if ref:
        q.append(('ref', ref))
    for k, v in (path.get('attributes') or {}).items():
        q.append((f'attributes[{k}]', str(v)))
    qs = urllib.parse.urlencode(q, safe='[]')
    return f"{base_url(cfg, path)}/cart/{lines}" + (f'?{qs}' if qs else '')


def describe_err(body):
    if isinstance(body, dict):
        return body.get('description') or body.get('message') or json.dumps(body)[:200]
    m = re.search(r'<title>(.*?)</title>', str(body), re.S | re.I)
    if m:
        return f'HTML page "{m.group(1).strip()}" (rate limit or bot check: raise --pause, or test this path in a browser)'
    return str(body)[:200]


def check_path(cfg, path, use_permalink=False):
    base = base_url(cfg, path)
    res = {'name': path['name'], 'status': None, 'ok': False, 'problems': []}
    if use_permalink:
        op = session(follow=False)
        st, body = call(op, permalink(cfg, path))
        res['status'] = st
        if st >= 400:
            res['problems'].append(f'permalink HTTP {st}: {describe_err(body)}')
            return res
    else:
        op = session()
        items = [{'id': int(l['variant']), 'quantity': int(l.get('qty', 1))} for l in path['lines']]
        st, body = call(op, f'{base}/cart/add.js', {'items': items})
        res['status'] = st
        if st != 200:
            res['problems'].append(f'add.js {st}: {describe_err(body)}')
            # name the culprit: try each line alone in its own fresh session
            for it in items:
                time.sleep(1.5)
                st1, b1 = call(session(), f'{base}/cart/add.js', {'items': [it]})
                if st1 != 200:
                    res['problems'].append(f"  variant {it['id']} -> {st1}: {describe_err(b1)}")
            return res
        if path.get('attributes'):
            st2, b2 = call(op, f'{base}/cart/update.js', {'attributes': path['attributes']})
            if st2 != 200:
                res['problems'].append(f'update.js {st2}: {describe_err(b2)}')

    st3, cart = call(op, f'{base}/cart.js')
    if st3 != 200 or not isinstance(cart, dict):
        res['problems'].append(f'cart.js {st3}: could not read the cart')
        return res
    got = {}
    for it in cart.get('items', []):
        got[int(it['variant_id'])] = got.get(int(it['variant_id']), 0) + int(it['quantity'])
    want = {}
    for l in path['lines']:
        want[int(l['variant'])] = want.get(int(l['variant']), 0) + int(l.get('qty', 1))
    if not got and use_permalink:
        res['problems'].append('cart is empty after the permalink (store may build the cart only on the checkout redirect); check this path in a browser')
    for v, q in want.items():
        if got.get(v) != q:
            res['problems'].append(f'variant {v}: expected qty {q}, cart has {got.get(v, 0)}')
    for v in got:
        if v not in want:
            res['problems'].append(f'unexpected line in cart: variant {v} x{got[v]}')
    total = cart.get('total_price', 0) / 100
    res['cart_total'] = total
    res['currency'] = cart.get('currency')
    exp = path.get('expect_total')
    if exp is not None and abs(total - float(exp)) > 0.009:
        res['problems'].append(f'total {total:.2f} != expected {float(exp):.2f} (catalogue price shown; an automatic discount may only apply at checkout)')
    attrs = cart.get('attributes') or {}
    for k, v in (path.get('attributes') or {}).items():
        if str(attrs.get(k, '')) != str(v):
            res['problems'].append(f'attribute {k}: expected {v!r}, cart has {attrs.get(k)!r}')
    res['attributes'] = attrs
    res['ok'] = not res['problems']
    return res


def main():
    ap = argparse.ArgumentParser(description='Verify every funnel path against the live Shopify cart (anonymous carts, nothing bought).')
    ap.add_argument('paths_json', help='Offer paths file, see templates/offer-paths.example.json')
    ap.add_argument('--permalink', action='store_true', help='Test the /cart/<v>:<q>?attributes[..] handoff link instead of /cart/add.js')
    ap.add_argument('--only', help='Only paths whose name contains this text')
    ap.add_argument('--report', help='Write the full results as JSON here')
    ap.add_argument('--print-links', action='store_true', help='Only print each path\'s cart permalink, no network calls')
    ap.add_argument('--pause', type=float, default=0.8, help='Seconds between paths (be gentle with the store), default 0.8')
    a = ap.parse_args()

    cfg = json.load(open(a.paths_json, encoding='utf-8'))
    paths = [p for p in cfg['paths'] if not a.only or a.only.lower() in p['name'].lower()]
    if a.print_links:
        for p in paths:
            print(f"{p['name']}\n  {permalink(cfg, p)}")
        return

    results, bad = [], 0
    for p in paths:
        r = check_path(cfg, p, a.permalink)
        results.append(r)
        flag = 'OK  ' if r['ok'] else 'FAIL'
        tot = f"{r.get('cart_total', 0):.2f} {r.get('currency') or ''}".strip() if 'cart_total' in r else '-'
        print(f"{flag} [{r['status']}] {p['name']:<36} {tot}")
        for pr in r['problems']:
            print(f'       {pr}')
        bad += not r['ok']
        time.sleep(a.pause)
    print(f"\n{len(paths) - bad}/{len(paths)} paths ok" + ('' if not bad else f', {bad} failing'))
    if a.report:
        json.dump(results, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
