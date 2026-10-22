#!/usr/bin/env python3
"""Builds index.html: the wave-2 ads shown the way they appear in the feed.

Same page furniture and the same card as shellyx-advertorials.vercel.app/ads-preview, so the two
can be read side by side, plus one thing that page does not have: the design family on every card,
because the whole point of this wave is that no two look alike.
"""
import html as H
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spec import ADS, LPS, PAGES, filename

ROOT = Path(__file__).parent
BASE = "https://shellyx-advertorials.vercel.app"
AV = {"shelly": "/img/brand/shelly.jpg", "signal": "/img/brand/signal.png",
      "martin": "/img/brand/martin.png", "andreas": "/img/brand/andreas.png",
      "elena": "/img/brand/elena.png"}
LINE_TITLE = {"flood": "Flood", "energy": "Energy", "rental": "Rental"}

CSS = """
@font-face{font-family:'Manrope';src:url('/font/manrope-semibold.ttf') format('truetype');font-weight:500 600;font-display:swap}
@font-face{font-family:'Manrope';src:url('/font/manrope-bold.ttf') format('truetype');font-weight:700;font-display:swap}
@font-face{font-family:'Manrope';src:url('/font/manrope-extrabold.ttf') format('truetype');font-weight:800;font-display:swap}
:root{--ink:#121519;--muted:#5C6672;--line:#E3EAF0;--tint:#F0F4F7;--blue:#4594D1;--link:#1F6FA8;--navy:#003C82;
  --stage:1220px;--pad:20px}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:400 16px/1.55 'Manrope',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;-webkit-font-smoothing:antialiased}
img{max-width:100%;display:block}
h1,h2,h3{font-weight:600;letter-spacing:-.01em;margin:0;text-wrap:balance}
p{margin:0}
a{color:var(--link)}
.fx-in{max-width:calc(var(--stage) + var(--pad)*2);margin:0 auto;padding-inline:var(--pad)}
.sh-ann{display:flex;align-items:center;justify-content:center;gap:8px;background:linear-gradient(90deg,#4594D1 0%,#0B4A8F 100%);color:#fff;font-size:14px;font-weight:600;padding:9px 16px;text-align:center}
.sh-head{padding:12px var(--pad) 0;max-width:calc(var(--stage) + var(--pad)*2);margin:0 auto}
.sh-bar{display:flex;align-items:center;gap:18px;background:#fff;border-radius:12px;box-shadow:0 6px 24px rgba(18,21,25,.10);padding:10px 18px;min-height:58px}
.sh-bar img{width:88px;height:24px}
.sh-bar nav{display:flex;gap:22px;flex-wrap:wrap}
.sh-bar nav a{color:var(--ink);text-decoration:none;font-weight:600;font-size:15.5px}
.ad-intro{padding-block:30px 6px}
.ad-intro h1{font-size:clamp(28px,4vw,40px);line-height:1.12}
.ad-intro p{font-size:17.5px;color:#3A434C;margin-top:12px;max-width:44em}
.ad-jump{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.ad-jump a,.ad-jump button{border:1px solid var(--line);border-radius:999px;padding:8px 14px;font:600 15px/1 'Manrope',sans-serif;text-decoration:none;color:var(--ink);background:#fff;cursor:pointer}
.ad-jump a:hover,.ad-jump button:hover{background:var(--tint)}
.ad-jump button[aria-pressed=true]{background:var(--navy);border-color:var(--navy);color:#fff}
.ad-note{margin-top:22px;border:1px solid var(--line);border-left:4px solid var(--navy);border-radius:10px;padding:16px 18px;background:var(--tint);font-size:16px;line-height:1.5;max-width:60em}
.ad-note b{font-weight:700}
.ad-h2{font-size:26px;margin-top:48px}
.ad-sub{color:var(--muted);margin-top:4px}
.ad-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:20px;align-items:start}
.ad{border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#fff}
.ad .meta{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line);background:var(--tint);font-size:12.5px;color:var(--muted)}
.ad .meta b{color:var(--ink);font-weight:600;font-size:13px}
.ad .meta .fam{background:#E8F2FA;color:#1F6FA8;border-radius:999px;padding:3px 9px;font-weight:700;font-size:12px}
.ad .pg{display:flex;align-items:center;gap:10px;padding:12px 14px 8px}
.ad .pg img{width:40px;height:40px;border-radius:50%;object-fit:cover;background:var(--tint)}
.ad .pg b{display:block;font-size:15px;font-weight:600;line-height:1.2}
.ad .pg span{display:block;font-size:12.5px;color:var(--muted)}
.ad .copy{padding:0 14px 12px;font-size:15px;line-height:1.5;white-space:pre-wrap}
.ad .shot{background:var(--tint)}
.ad .shot img{width:100%}
.ad .car{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none}
.ad .car::-webkit-scrollbar{display:none}
.ad .car figure{flex:0 0 78%;min-width:0;margin:0;scroll-snap-align:start;border-right:1px solid var(--line)}
.ad .car figcaption{font-size:13.5px;font-weight:600;padding:8px 12px;background:#fff}
.ad .link{display:flex;align-items:center;gap:12px;padding:12px 14px;background:#F2F4F7;border-top:1px solid var(--line)}
.ad .link .t{min-width:0;flex:1}
.ad .link .dom{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ad .link b{display:block;font-size:15px;line-height:1.25;margin-top:2px}
.ad .link span.desc{display:block;font-size:13.5px;color:var(--muted);margin-top:2px}
.ad .cta{flex:0 0 auto;background:#E4E6EB;border-radius:8px;padding:9px 14px;font-size:14px;font-weight:600;white-space:nowrap}
.ad .go{display:block;padding:10px 14px;font-size:13.5px;border-top:1px solid var(--line)}
.ad .go a{font-weight:600}
.ad[hidden]{display:none}
footer{margin-top:64px;background:var(--tint);border-top:1px solid var(--line);padding:30px 0;font-size:14px;color:var(--muted)}
@media (max-width:1020px){.ad-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.ad-grid{grid-template-columns:1fr}.ad .car figure{flex:0 0 86%}}
"""

JS = """
const btns=[...document.querySelectorAll('[data-fam]')];
btns.forEach(b=>b.onclick=()=>{
  const on=b.getAttribute('aria-pressed')==='true';
  btns.forEach(x=>x.setAttribute('aria-pressed','false'));
  b.setAttribute('aria-pressed', on?'false':'true');
  const want=on?null:b.dataset.fam;
  document.querySelectorAll('.ad').forEach(a=>{a.hidden=want&&a.dataset.fam!==want});
  document.querySelectorAll('section.line').forEach(s=>{
    s.hidden=!s.querySelector('.ad:not([hidden])');
  });
});
"""


def card(a):
    lp_label, ident = LPS[a["lp"]]
    pg = PAGES[ident]
    url = (f"{BASE}/{a['lp']}?utm_source=facebook&utm_medium=paid"
           f"&utm_campaign=shellyx-{a['line']}&utm_term=broad-{a['lp']}&utm_content={a['code']}")
    fmt = "carousel" if a.get("carousel") else "single image"
    if a.get("carousel"):
        media = '<div class="car">' + "".join(
            f'<figure><img src="/img/ads/{filename(a, i)}" alt="" loading="lazy">'
            f'<figcaption>{H.escape(sl["cap"])}</figcaption></figure>'
            for i, sl in enumerate(a["carousel"][:4], 1)) + "</div>"
    else:
        media = f'<div class="shot"><img src="/img/ads/{filename(a)}" alt="" loading="lazy"></div>'
    return f"""<article class="ad" id="{a['code']}" data-fam="{H.escape(a['fam'])}">
<div class="meta"><b class="code">{a['code']}</b><span class="fam">{H.escape(a['fam'])}</span>
<span>{fmt}</span><span>{a['ratio'].replace('x', ':')}</span><span>goes to: {H.escape(lp_label)}</span></div>
<div class="pg"><img src="{AV[ident]}" alt=""><div><b>{H.escape(pg['name'])}</b><span>Sponsored</span></div></div>
<p class="copy">{H.escape(a['copy'])}</p>
{media}
<div class="link"><div class="t"><span class="dom">shellyx-advertorials.vercel.app</span>
<b>{H.escape(a['hl'])}</b><span class="desc">{H.escape(a['desc'])}</span></div>
<span class="cta">{H.escape(a['cta'])}</span></div>
<span class="go"><a href="{H.escape(url)}" target="_blank" rel="noopener">Open the page this ad points at</a></span>
</article>"""


def build():
    fams = sorted({a["fam"] for a in ADS})
    chips = "".join(f'<button data-fam="{H.escape(f)}" aria-pressed="false">{H.escape(f)}</button>' for f in fams)
    secs = ""
    for line in ("flood", "energy", "rental"):
        ads = [a for a in ADS if a["line"] == line]
        car = len([a for a in ads if a.get("carousel")])
        secs += (f'<section class="fx-sec line"><h2 class="ad-h2" id="{line}">{LINE_TITLE[line]}</h2>'
                 f'<p class="ad-sub">{len(ads)} ads, {len(ads)-car} single image and {car} carousel, '
                 f'across {len({a["fam"] for a in ads})} design families.</p>'
                 f'<div class="ad-grid">' + "".join(card(a) for a in ads) + "</div></section>")

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Shelly funnels: the second wave of ads</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3E&#128227;%3C/text%3E%3C/svg%3E">
<style>{CSS}</style></head><body>
<div class="sh-ann">FREE DELIVERY for orders over 79&euro;</div>
<header class="sh-head"><div class="sh-bar">
<img src="/img/brand/shelly-logo.svg" alt="Shelly">
<nav><a href="{BASE}/review" target="_blank">The first wave</a>
<a href="{BASE}/ads-preview" target="_blank">The 54 live ads</a>
<a href="#flood">Flood</a><a href="#energy">Energy</a><a href="#rental">Rental</a></nav>
</div></header>
<main class="fx-in">
<section class="ad-intro"><h1>The second wave, in {len(fams)} design families</h1>
<p>Sixty new ads for the same three lines and the same twelve pages. The first wave was
fifty-four ads in a single treatment: a candid phone photograph with no text on it. Every ad
below is deliberately something else, because Meta discounts near duplicates and rewards the
same message in visually unrelated executions.</p>
<div class="ad-jump"><a href="#flood">Flood</a><a href="#energy">Energy</a><a href="#rental">Rental</a></div>
<div class="ad-jump" style="margin-top:10px">{chips}</div>
<div class="ad-note"><b>How to read this.</b> Every card names its design family, its format and
the page it sends people to. Who posts the ad decides what the design may be: the Shelly page may
carry brand and product, Home Signal is a publication and carries neither, and the three personal
blogs carry neither. Tap a family above to see only that treatment.</div>
</section>
{secs}
</main>
<footer><div class="fx-in">Nothing here is live and no page is indexed. Prices in EUR.
Flood 55.90, Energy 69.90, Rental 89.90, all per the approved offer table.</div></footer>
<script>{JS}</script></body></html>"""
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"index.html: {len(ADS)} cards, {len(fams)} families, {len(page)//1024} KB")


if __name__ == "__main__":
    build()
