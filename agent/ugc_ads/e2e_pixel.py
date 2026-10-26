import asyncio, re, sys
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
SL = ["miehme-vsyaka-vecher","7-prichini-detska-chetka","3-ot-5-strani","zabolekarite-savetvat","7-prichini-nordics"]
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
async def run(consent):
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        for s in SL:
            ctx = await b.new_context(user_agent=UA, viewport={'width':390,'height':844})
            if consent: await ctx.add_cookies([{'name':'cmplz_marketing','value':'allow','domain':'wearenordics.com','path':'/'}])
            pg = await ctx.new_page(); fb = []; carts = []
            pg.on('request', lambda r: fb.append(r.url) if 'facebook.com/tr' in r.url else (carts.append(r.url) if 'anchor_cart=' in r.url else None))
            await pg.goto(f'https://wearenordics.com/lp/{s}/?utm_source=facebook&utm_medium=paid&utm_campaign=kids_adv_test&utm_content=TEST01&fbclid=ANCHORE2E{s[:6]}', wait_until='load')
            await pg.wait_for_timeout(2500)
            ev = [parse_qs(urlparse(u).query).get('ev',[''])[0] for u in fb]
            a = pg.locator('a[href*="anchor_cart="]').first
            await a.scroll_into_view_if_needed(); await a.click()
            await pg.wait_for_load_state('load'); await pg.wait_for_timeout(2500)
            q = parse_qs(urlparse(carts[0]).query) if carts else {}
            ok = q.get('fbclid',[''])[0].startswith('ANCHORE2E') and q.get('utm_content',[''])[0]=='TEST01'
            print(('consent ' if consent else 'no-cons ')+s, '| LP pixel:', ev or 'none', '| cart link fbclid+utm:', 'OK' if ok else 'MISSING', {k:v[0] for k,v in q.items() if k!='anchor_cart'}, '| end:', urlparse(pg.url).path)
            await ctx.close()
        await b.close()
asyncio.run(run(False)); asyncio.run(run(True))
