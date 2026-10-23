#!/usr/bin/env python3
"""Load every funnel page in headless Chromium and report problems. Read-only; trackers are blocked.

Checks per URL: HTTP status 200, uncaught page errors, console errors, broken images (all images forced
to load eagerly), horizontal scroll at the viewport width. Exit code 1 if any page has a problem.

Needs Playwright: pip3 install playwright && python3 -m playwright install chromium

Input: the QA config (templates/qa-config.example.json: base_url, pages, viewport, block_patterns),
or --urls with full URLs or paths. Examples:
  python3 qa_pages.py qa-config.json
  python3 qa_pages.py qa-config.json --desktop --shots qa/shots
  python3 qa_pages.py --base https://example.com --urls /xx/article/a1 /xx/checkout
"""
import argparse
import json
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('config', nargs='?', help='QA config JSON')
    ap.add_argument('--base', help='base URL (overrides config base_url)')
    ap.add_argument('--urls', nargs='*', help='URLs or paths to check instead of config pages')
    ap.add_argument('--desktop', action='store_true', help='1366 x 900 instead of the mobile viewport')
    ap.add_argument('--shots', help='folder for a top-of-page screenshot of each URL (costs tokens to look at; use sparingly)')
    ap.add_argument('--ignore-console', default='', help='regex of console messages to ignore')
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding='utf8')) if a.config else {}
    base = (a.base or cfg.get('base_url') or '').rstrip('/')
    paths = a.urls or cfg.get('pages') or []
    if not paths:
        sys.exit('No pages: give a config with "pages" or --urls')
    urls = [p if p.startswith('http') else base + p for p in paths]
    block = cfg.get('block_patterns') or [r'facebook\.(net|com)', r'clarity\.ms', r'google-analytics\.com', r'googletagmanager\.com']
    block_re = re.compile('|'.join(block))
    ign = re.compile(a.ignore_console) if a.ignore_console else None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit('Playwright is missing: pip3 install playwright && python3 -m playwright install chromium')

    vp = {'width': 1366, 'height': 900} if a.desktop else cfg.get('viewport', {'width': 390, 'height': 844})
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
    bad = 0
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=vp, is_mobile=not a.desktop, has_touch=not a.desktop)
        ctx.route(block_re, lambda r: r.abort())
        for u in urls:
            p = ctx.new_page()
            errs, cons = [], []
            p.on('pageerror', lambda e: errs.append(str(e)))
            p.on('console', lambda m: cons.append(m.text) if m.type == 'error' else None)
            try:
                r = p.goto(u, wait_until='networkidle', timeout=45000)
                status = r.status if r else 0
            except Exception as e:
                status, errs = 0, [f'load failed: {e}']
            broken, hscroll = [], False
            if status:
                broken = p.evaluate("""async () => {
                    for (const i of document.images) i.loading = 'eager';
                    await new Promise(r => setTimeout(r, 1500));
                    return [...document.images].filter(i => i.complete && i.naturalWidth === 0 && !i.closest('[hidden]'))
                        .map(i => i.getAttribute('src'));
                }""")
                hscroll = p.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
                if a.shots:
                    name = re.sub(r'[^a-z0-9]+', '-', u.split('://', 1)[-1].lower()).strip('-')[:80]
                    p.screenshot(path=os.path.join(a.shots, name + '.png'))
            # blocked tracker requests show up as console errors; drop those
            cons = [c for c in cons if not re.search(r'net::ERR_FAILED|ERR_BLOCKED', c) and not (ign and ign.search(c))]
            problem = status != 200 or errs or cons or broken or hscroll
            if problem:
                bad += 1
                print(f'PROBLEM {u}  status={status}')
                for e in errs[:3]:
                    print('   page error:', e[:200])
                for c in cons[:3]:
                    print('   console:', c[:200])
                for s in broken[:5]:
                    print('   broken image:', s)
                if hscroll:
                    print('   horizontal scroll at', vp['width'], 'px')
            else:
                print(f'ok      {u}')
            p.close()
        b.close()
    print(f'\nchecked {len(urls)} pages, problems: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
