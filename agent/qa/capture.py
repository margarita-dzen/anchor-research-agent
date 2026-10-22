"""Снимка + DOM текст + списък на секциите на произволна страница, на 390 и 1440 px (headless Chromium).

    python3 agent/qa/capture.py <url> --out qa_out/original [--widths 390,1440] [--max-height 16000]

Какво прави:
  1. Отваря страницата само headless (никога видим Chrome), скролва до дъното заради lazy load.
  2. Ако страницата скролва във вътрешен контейнер (Canva и подобни: документът е ~900 px), намира контейнера,
     скролва него и зашива снимката (урокът от ATOPI Karbonoir, `capture_scroll.py`).
  3. Скрива фиксирани попъпи (бисквитки, Klaviyo), които покриват екрана.
  4. Записва за всяка ширина: full_<w>.png + full_<w>.jpg (до --max-height px), text_<w>.txt (DOM текстът),
     outline_<w>.json (секциите отгоре надолу: y, височина, заглавие, брой img/video/бутони/li, повтарящи се карти,
     цвят на фона, шрифтове, цени, въпроси, звезди).

Секциите се режат по заглавията (h1-h4 или текст с шрифт >= 1,3 пъти основния) и по цветни ленти на цялата ширина.
Хедърът и футърът на магазина не влизат (клонингите ги скриват), освен с --keep-chrome.

Вход може да е и папка със запазен оригинал (`src/` с page_<w>.html и full_<w>.png от capture.py на клонингите):
тогава HTML-ът се зарежда на оригиналния адрес (canonical) с изключен JS, а снимката е тяхната full_<w>.png.
"""
import argparse, glob, io, json, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
DEFAULT_MAX_HEIGHT = 16000
CHUNK = 4000  # височина на едно парче при снимането (Chromium чупи снимки > 16384 px)

FIND_SCROLLER_JS = r"""() => {
  const vh = innerHeight, dh = document.documentElement.scrollHeight;
  let best = null, h = 0;
  for (const e of document.querySelectorAll('body *')) {
    if (e.clientHeight < vh * 0.6) continue;
    const s = getComputedStyle(e);
    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && e.scrollHeight > e.clientHeight * 1.5 && e.scrollHeight > h) {
      h = e.scrollHeight; best = e;
    }
  }
  if (best && h > dh * 1.3) {
    best.setAttribute('data-qa-scroller', '1');
    const r = best.getBoundingClientRect();
    return {h: h, ch: best.clientHeight, top: r.top, left: r.left, width: best.clientWidth};
  }
  return null;
}"""

HIDE_POPUPS_JS = r"""() => {
  let n = 0; const area = innerWidth * innerHeight;
  for (const e of document.querySelectorAll('body *')) {
    const s = getComputedStyle(e);
    if (s.position !== 'fixed' || s.display === 'none') continue;
    const r = e.getBoundingClientRect();
    const big = r.width * r.height > area * 0.25;
    const named = /popup|modal|klaviyo|cookie|consent|newsletter|overlay/i.test((e.className && e.className.baseVal === undefined ? e.className : '') + ' ' + e.id);
    if (big || (named && r.height > 80)) { e.style.setProperty('display', 'none', 'important'); n++; }
  }
  document.documentElement.style.overflow = ''; if (document.body) document.body.style.overflow = '';
  return n;
}"""

OUTLINE_JS = r"""(opt) => {
  const sc = document.querySelector('[data-qa-scroller]');
  const scR = sc ? sc.getBoundingClientRect() : null;
  const offY = sc ? (sc.scrollTop - scR.top) : window.scrollY;
  const W = sc ? sc.clientWidth : document.documentElement.clientWidth;
  const H = sc ? sc.scrollHeight : Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0);
  const root = sc || document.body;
  const all = [...root.querySelectorAll('*')];
  const cache = new Map();
  const cs = e => { let s = cache.get(e); if (!s) { s = getComputedStyle(e); cache.set(e, s); } return s; };
  const rect = e => { const r = e.getBoundingClientRect(); return {x: r.left, y: r.top + offY, w: r.width, h: r.height}; };
  const shown = (e, r) => { if (r.w < 1 || r.h < 1) return false; const s = cs(e); return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0.05; };
  const transparent = c => !c || c === 'transparent' || /rgba\(.*,\s*0\)$/.test(c);
  const fixedAnc = e => { for (let i = 0; e && i < 8; i++, e = e.parentElement) { const p = cs(e).position; if (p === 'fixed') return true; } return false; };
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'META', 'LINK', 'HEAD']);

  // хедър/футър на магазина
  const inMain = e => !!e.closest('main, #MainContent, article, [role=main]');
  let y0 = 0, y1 = H;
  if (!opt.keepChrome && !sc) {
    for (const e of document.querySelectorAll('header, [role=banner], .shopify-section-group-header-group, #shopify-section-header, .announcement-bar-section')) {
      if (inMain(e)) continue;  // <header> на самия адвърториал не е хедър на магазина
      const r = rect(e); if (shown(e, r) && r.y < 300 && r.h < 400 && cs(e).position !== 'fixed') y0 = Math.max(y0, r.y + r.h);
    }
    const h1 = [...document.querySelectorAll('h1')].map(e => rect(e)).find(r => r.h > 0);
    if (h1 && y0 > h1.y) y0 = Math.max(0, Math.floor(h1.y) - 10);  // хедърът не може да е под H1
    for (const e of document.querySelectorAll('footer, [role=contentinfo], .shopify-section-group-footer-group, #shopify-section-footer')) {
      if (inMain(e)) continue;
      const r = rect(e); if (shown(e, r) && r.y + r.h >= H - 80 && r.y > H * 0.5) y1 = Math.min(y1, r.y);
    }
  }

  // носители на текст
  const carriers = [];
  for (const e of all) {
    if (SKIP.has(e.tagName)) continue;
    let t = '';
    for (const n of e.childNodes) if (n.nodeType === 3) t += n.textContent;
    t = t.replace(/\s+/g, ' ').trim();
    if (!t) continue;
    const r = rect(e); if (!shown(e, r)) continue;
    const s = cs(e);
    carriers.push({e, r, t, fs: parseFloat(s.fontSize) || 16, fw: parseInt(s.fontWeight) || 400, ff: (s.fontFamily || '').split(',')[0].replace(/["']/g, '').trim()});
  }
  const fsW = new Map();
  for (const c of carriers) fsW.set(c.fs, (fsW.get(c.fs) || 0) + c.t.length);
  let base = 16, bw = 0; for (const [k, v] of fsW) if (v > bw) { bw = v; base = k; }
  const thr = Math.max(base * 1.3, base + 4);

  const blockOf = e => { for (let i = 0; e && i < 4; i++, e = e.parentElement) { const d = cs(e).display; if (d !== 'inline' && d !== 'contents') return e; } return e; };
  const heads = [];
  const seen = new Set();
  const addHead = (e, tag) => {
    if (!e || seen.has(e)) return; seen.add(e);
    const r = rect(e); if (!shown(e, r) || fixedAnc(e)) return;
    if (e.closest('summary, details, button, a, label, [aria-expanded], [role=button], [role=tab]')) return;  // FAQ въпросите не режат секции
    const tt = (e.innerText || '').trim();
    if (tag === 'big' && tt.length <= 40) for (let p = e.parentElement, i = 0; p && i < 4; p = p.parentElement, i++) {  // името в карта на отзив не реже секция
      const it = p.innerText || '';
      if (it.length < 900 && (/[★⭐]/.test(it) || p.querySelector('[class*=star i], [class*=rating i]'))) return;
    }
    const t = (e.innerText || '').replace(/\s+/g, ' ').trim();
    if (t.length < 2 || t.length > 220 || (t.match(/\p{L}/gu) || []).length < 3) return;
    if (r.y < y0 - 2 || r.y > y1) return;
    heads.push({y: Math.round(r.y), t: t.slice(0, 160), tag: tag, fs: parseFloat(cs(e).fontSize) || 16});
  };
  for (const e of root.querySelectorAll('h1,h2,h3,h4')) addHead(e, e.tagName.toLowerCase());
  for (const c of carriers) if (c.fs >= thr && (c.fw >= 500 || c.fs >= base * 1.6) && (c.t.match(/\p{L}/gu) || []).length >= 3) addHead(blockOf(c.e), 'big');

  // цветни ленти на цялата ширина
  const bodyBg = cs(document.body).backgroundColor, htmlBg = cs(document.documentElement).backgroundColor;
  const bands = [];
  for (const e of all) {
    const s = cs(e); const bg = s.backgroundColor;
    if (transparent(bg) || bg === bodyBg || (transparent(bodyBg) && bg === htmlBg) || bg === 'rgb(255, 255, 255)' && (transparent(bodyBg) || bodyBg === 'rgb(255, 255, 255)')) continue;
    const r = rect(e); if (r.w < W * 0.97 || r.x > 4 || r.h < 120 || !shown(e, r) || s.position === 'fixed') continue;
    if (r.y + r.h < y0 || r.y > y1) continue;
    bands.push([Math.round(r.y), Math.round(r.y + r.h)]);
  }
  return {W, H, y0: Math.round(y0), y1: Math.round(y1), base_fs: base, heads, bands,
          scroller: !!sc,
          // броячите се смятат в Python по позициите
          items: (() => {
            const out = [];
            const push = (kind, e, r) => out.push([kind, Math.round(r.y + r.h / 2), Math.round(r.h)]);
            for (const e of root.querySelectorAll('img')) { const r = rect(e); if (r.w >= 40 && r.h >= 40 && shown(e, r) && !fixedAnc(e)) push('img', e, r); }
            for (const e of root.querySelectorAll('video, iframe')) {
              const r = rect(e); if (!shown(e, r) || r.w < 80) continue;
              if (e.tagName === 'IFRAME' && !/youtube|vimeo|wistia|vidalytics|player|video|loom|tiktok/i.test(e.src || '')) continue;
              push('video', e, r);
            }
            for (const e of all) {
              const s = cs(e);
              if (s.backgroundImage && s.backgroundImage.includes('url(') && e.tagName !== 'IMG') {
                const r = rect(e); if (r.w >= 100 && r.h >= 100 && shown(e, r) && !fixedAnc(e)) push('bgimg', e, r);
              }
            }
            for (const e of root.querySelectorAll('button, input[type=submit], input[type=button], a, [role=button]')) {
              const r = rect(e); if (!shown(e, r) || r.h < 28 || r.w < 60 || fixedAnc(e)) continue;
              const t = (e.innerText || e.value || '').trim();
              if (t.length < 2 || t.length > 60) continue;
              const s = cs(e);
              const filled = !transparent(s.backgroundColor) || (parseFloat(s.borderTopWidth) >= 1 && s.borderTopStyle !== 'none');
              if (e.tagName === 'A' && !filled && !/btn|button/i.test(String(e.className))) continue;
              push('button', e, r);
            }
            for (const e of root.querySelectorAll('li')) {
              const r = rect(e); if (!shown(e, r) || e.closest('nav, header, footer') || r.h < 12) continue;
              if (!(e.innerText || '').trim() && !e.querySelector('img')) continue;
              push('li', e, r);
            }
            for (const e of root.querySelectorAll('details, summary, [aria-expanded]')) { const r = rect(e); if (shown(e, r)) push('details', e, r); }
            for (const e of root.querySelectorAll('input:not([type=hidden]), select, textarea')) { const r = rect(e); if (shown(e, r)) push('input', e, r); }
            for (const e of all) {
              const cls = String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || '');
              if (/(^|[-_ ])(stars?|rating|jdgm-star)([-_ ]|$)/i.test(cls) && e.children.length <= 6) { const r = rect(e); if (shown(e, r)) push('star', e, r); }
            }
            for (const c of carriers) {
              const stars = (c.t.match(/[★⭐]/g) || []).length; if (stars) push('star', c.e, c.r);
              if (/(\d+[.,]\d{2}\s?(€|лв|lei|kr|zł|\$|eur))|([€$£]\s?\d+)/i.test(c.t)) push('price', c.e, c.r);
              if (c.t.length < 200 && /\?\s*$/.test(c.t)) push('question', c.e, c.r);
              out.push(['text', Math.round(c.r.y + c.r.h / 2), c.t.length, c.ff, c.t.slice(0, 120)]);
            }
            // повтарящи се карти (отзиви, причини, мрежи): деца на един родител с еднакъв таг+клас
            let pi = 0;
            for (const p of all) {
              pi++;
              if (p.children.length < 3) continue;
              const groups = new Map();
              for (const ch of p.children) {
                const cls = String(ch.className && ch.className.baseVal === undefined ? ch.className : '').trim();
                if (!cls && !['LI', 'ARTICLE', 'FIGURE', 'A'].includes(ch.tagName)) continue;
                if (/^(P|SPAN|BR|H\d|STRONG|EM|B|I)$/.test(ch.tagName)) continue;
                const r = rect(ch); if (r.h < 40 || r.w < 60 || !shown(ch, r)) continue;
                const k = ch.tagName + '.' + cls.split(/\s+/).filter(x => !/active|current|selected|visible|is-|aos|animate/.test(x)).sort().join('.');
                if (!groups.has(k)) groups.set(k, []);
                groups.get(k).push([Math.round(r.y + r.h / 2), r.h]);
              }
              let gid = 0;
              for (const [k, g] of groups) {
                if (g.length < 3) continue;
                const hs = g.map(x => x[1]);
                if (Math.max(...hs) / Math.max(1, Math.min(...hs)) > 2.5) continue;  // обвивки на page builder, не карти
                const ys = g.map(x => x[0]); gid++; for (const y of ys) out.push(['rep', y, ys.length, k + '#' + pi + ':' + gid]); }
            }
            return out;
          })()};
}"""


# ---------- чиста логика (тества се без браузър) ----------

def build_sections(raw, min_h=60):
    """Сурови заглавия/ленти/елементи от OUTLINE_JS → списък секции с броячи."""
    y0, y1 = raw.get("y0", 0), raw.get("y1", raw["H"])
    cuts = {y0, y1}
    for h in raw["heads"]:
        cuts.add(h["y"])
    for a, b in raw["bands"]:
        cuts.add(a); cuts.add(b)
    cuts = sorted(c for c in cuts if y0 <= c <= y1)
    merged = []
    for c in cuts:  # слепва граници на < 30 px
        if merged and c - merged[-1] < 30:
            continue
        merged.append(c)
    if merged[-1] != y1:
        merged[-1] = y1
    spans = [[a, b] for a, b in zip(merged, merged[1:])]
    out = []  # малките парчета (отстъп преди заглавие) отиват към следващата секция
    carry = None
    for a, b in spans:
        if carry is not None:
            a = carry; carry = None
        if b - a < min_h:
            carry = a
            continue
        out.append([a, b])
    if carry is not None:
        if out:
            out[-1][1] = y1
        else:
            out.append([carry, y1])
    heads = sorted(raw["heads"], key=lambda h: h["y"])
    secs = []
    for a, b in out:
        s = dict(y=a, h=b - a, heading="", heading_tag="", img=0, bgimg=0, video=0, button=0, li=0, details=0,
                 input=0, star=0, price=0, question=0, repeat=0, text_len=0, fonts=[], text="")
        hs = [h for h in heads if a - 2 <= h["y"] < b]
        if hs:
            top = max(hs[:3], key=lambda h: h["fs"])  # кикер над H1: взима по-едрото
            s["heading"], s["heading_tag"] = top["t"], top["tag"]
        secs.append(s)

    def find(y):
        for s in secs:
            if s["y"] <= y < s["y"] + s["h"]:
                return s
        return None

    fonts = [Counter() for _ in secs]
    texts = [[] for _ in secs]
    reps = [dict() for _ in secs]
    for it in raw["items"]:
        kind, y = it[0], it[1]
        s = find(y)
        if s is None:
            continue
        i = secs.index(s)
        if kind == "text":
            s["text_len"] += it[2]
            if it[3]:
                fonts[i][it[3]] += it[2]
            if sum(len(t) for t in texts[i]) < 300:
                texts[i].append(it[4])
        elif kind == "rep":
            reps[i][it[3]] = reps[i].get(it[3], 0) + 1
        elif kind in s:
            s[kind] += 1
    for i, s in enumerate(secs):
        s["fonts"] = [f for f, _ in fonts[i].most_common(2)]
        s["text"] = " | ".join(texts[i])[:300]
        best = max(reps[i].values()) if reps[i] else 0
        s["repeat"] = best if best >= 2 else 0
        s["num"] = heading_number(s["heading"])
        s["type"] = classify(s)
    return secs


NUM_RE = re.compile(r"^\s*(?:(?:#|№|no\.?|nr\.?|n°)\s*(\d{1,2})\b|(\d{1,2})\s*[.)/:\-–](?!\d))|"
                    r"(?:причина|reason|grund|motiv|motivul|стъпка|step|schritt|pasul|tip|съвет|#|№)\s*(?:№|#|nr\.?\s*)?(\d{1,2})\b",
                    re.I)


def heading_number(t):
    """Номер на точка в заглавие: „3. Причина“, „#3“, „Причина №3“, „Reason 3“ → 3."""
    m = NUM_RE.search(t or "")
    if not m:
        return None
    n = int(next(g for g in m.groups() if g))
    return n if 0 < n <= 30 else None


def classify(s):
    media = s["img"] + s["bgimg"]
    if s["details"] >= 2 or s["question"] >= 3:
        return "faq"
    if s["price"] >= 2 or (s["price"] >= 1 and (s["button"] >= 1 or s["input"] >= 1)):
        return "offer"
    if s["star"] >= 3 and s["text_len"] > 120:
        return "reviews"
    if s["video"] >= 1:
        return "video"
    if s["repeat"] >= 3 or s["li"] >= 3:
        return "list"
    if media >= 3:
        return "gallery"
    if s["button"] >= 1 and s["text_len"] < 300:
        return "cta"
    if media >= 1:
        return "image"
    return "text"


def dominant_color(img):
    """Най-честият цвят на парче (закръглен), като #rrggbb."""
    if img is None or img.width == 0 or img.height == 0:
        return None
    small = img.convert("RGB").resize((24, 24))
    c = Counter(tuple((v // 16) * 16 + 8 for v in px) for px in small.getdata())
    r, g, b = c.most_common(1)[0][0]
    return "#%02x%02x%02x" % (min(r, 255), min(g, 255), min(b, 255))


# ---------- браузър ----------

def new_context(browser, width, js=True):
    mob = width < 700
    return browser.new_context(viewport={"width": width, "height": 844 if mob else 900}, is_mobile=mob, has_touch=mob,
                               device_scale_factor=1, user_agent=IPHONE_UA if mob else None,
                               java_script_enabled=js, ignore_https_errors=True)


def lazy_scroll(page, scroller=False, max_px=60000, budget_s=40):
    """Скролва до дъното (или до max_px) на стъпки, за да заредят lazy снимките."""
    t0 = time.time()
    get_h = ("document.querySelector('[data-qa-scroller]').scrollHeight" if scroller
             else "Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)")
    step = 600
    y = 0
    H = page.evaluate(get_h)
    while y < min(H, max_px) and time.time() - t0 < budget_s:
        y += step
        if scroller:
            page.evaluate(f"document.querySelector('[data-qa-scroller]').scrollTop={y}")
        else:
            page.evaluate(f"window.scrollTo(0,{y})")
        time.sleep(0.2)
        H = page.evaluate(get_h)
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    if scroller:
        page.evaluate("document.querySelector('[data-qa-scroller]').scrollTop=0")
    else:
        page.evaluate("window.scrollTo(0,0)")
    time.sleep(0.8)
    return H


def open_page(browser, url, width, html=None, js=True, wait=3.0, errors=None, on_page=None):
    """Отваря url (или подменя отговора му със запазен html) и връща (context, page, scroller_info)."""
    ctx = new_context(browser, width, js=js)
    page = ctx.new_page()
    if errors is not None:
        page.on("pageerror", lambda e: errors.append({"type": "pageerror", "text": str(e)[:300], "url": ""}))
        page.on("console", lambda m: errors.append({"type": "console", "text": m.text[:300], "url": (m.location or {}).get("url", "")})
                if m.type == "error" else None)
    if on_page:
        on_page(page)
    if html is not None:
        def handler(route):
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
        page.route(url, handler)
    resp = page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.qa_status = resp.status if resp else None
    try:
        page.wait_for_load_state("load", timeout=30000)
    except Exception:
        pass
    time.sleep(wait)
    # банерът за бисквитки, лентата на preview темата и поп-ъпите не са част от страницата (тест 22.10: влизаха в снимките и блокираха клика)
    page.evaluate("""()=>{for(const s of ['#shopify-pc__banner','.shopify-pc__banner__dialog','#preview-bar-iframe','#PBarNextFrameWrapper',
      'iframe[src*=preview_bar]','#onetrust-banner-sdk','#CybotCookiebotDialog','.cc-window','[id*=cookie-banner]','[class*=cookie-consent]'])
      document.querySelectorAll(s).forEach(e=>e.remove())}""")
    sc = page.evaluate(FIND_SCROLLER_JS)
    return ctx, page, sc


def screenshot_full(page, H, width, sc=None, max_height=DEFAULT_MAX_HEIGHT):
    """Снимка на цялата страница на парчета (или зашита от вътрешния контейнер), до max_height px."""
    from PIL import Image
    target = min(H, max_height)
    if sc:
        ch = sc["ch"]
        canvas = Image.new("RGB", (int(sc["width"]), int(target)), "white")
        y = 0
        while y < target:
            page.evaluate(f"document.querySelector('[data-qa-scroller]').scrollTop={y}")
            time.sleep(0.9)
            real = page.evaluate("document.querySelector('[data-qa-scroller]').scrollTop")
            shot = Image.open(io.BytesIO(page.screenshot(clip={"x": sc["left"], "y": sc["top"], "width": sc["width"], "height": ch})))
            shot = shot.resize((int(sc["width"]), int(ch)))
            canvas.paste(shot, (0, int(real)))
            if real + ch >= sc["h"]:
                break
            y += ch
        page.evaluate("document.querySelector('[data-qa-scroller]').scrollTop=0")
        return canvas
    canvas = Image.new("RGB", (width, int(target)), "white")
    y = 0
    while y < target:
        h = min(CHUNK, target - y)
        png = page.screenshot(full_page=True, clip={"x": 0, "y": y, "width": width, "height": h}, timeout=120000)
        part = Image.open(io.BytesIO(png))
        if part.width != width:
            part = part.resize((width, int(part.height * width / part.width)))
        canvas.paste(part, (0, y))
        y += h
    return canvas


def page_text(page):
    return page.evaluate("(document.querySelector('[data-qa-scroller]') || document.body).innerText")


def outline_from_page(page, keep_chrome=False):
    raw = page.evaluate(OUTLINE_JS, {"keepChrome": keep_chrome})
    secs = build_sections(raw)
    return raw, secs


def add_colors(secs, img, scale=1.0):
    for s in secs:
        top = int(s["y"] * scale)
        bot = int((s["y"] + s["h"]) * scale)
        if img is not None and top < img.height:
            s["bg"] = dominant_color(img.crop((0, top, img.width, min(bot, img.height))))
        else:
            s["bg"] = None


def capture_one(browser, url, width, out_dir, max_height=DEFAULT_MAX_HEIGHT, keep_chrome=False, html=None,
                src_png=None, save=True):
    """Една ширина: връща outline dict (+ PIL снимка в ключ '_img')."""
    from PIL import Image
    errors = []
    js = html is None
    ctx, page, sc = open_page(browser, url, width, html=html, js=js, errors=errors)
    try:
        if js:
            H = lazy_scroll(page, scroller=bool(sc))
        page.evaluate(HIDE_POPUPS_JS)
        time.sleep(0.4)
        sc = page.evaluate(FIND_SCROLLER_JS) or sc
        raw, secs = outline_from_page(page, keep_chrome=keep_chrome)
        H = raw["H"]
        note = []
        status = getattr(page, "qa_status", None)
        title = page.title()
        if (status and status >= 400) or re.match(r"^\s*404\b", title or ""):
            note.append(f"ВНИМАНИЕ: страницата връща HTTP {status} („{title[:60]}“). Сравнението е безсмислено.")
        if sc:
            note.append(f"вътрешен скрол контейнер: документът е {page.evaluate('document.documentElement.scrollHeight')} px, "
                        f"съдържанието {sc['h']} px, снимката е зашита")
        img = None
        scale = 1.0
        if src_png and os.path.exists(src_png):
            img = Image.open(src_png).convert("RGB")
            scale = img.width / float(width)
            if abs(img.height / scale - H) / max(H, 1) > 0.15:
                note.append(f"запазената снимка ({int(img.height / scale)} px) не съвпада с HTML-а ({H} px): снимам HTML-а наново")
                img = None
            elif img.height / scale > max_height:
                img = img.crop((0, 0, img.width, int(max_height * scale)))
        if img is None:
            scale = 1.0
            img = screenshot_full(page, H, width, sc=sc, max_height=max_height)
        capped = H > max_height
        if capped:
            note.append(f"страницата е {H} px, снимката е отрязана на {max_height} px (секциите след това са само по DOM)")
        if H < 1300 and not sc:
            note.append(f"ВНИМАНИЕ: страницата е само {H} px висока. Провери дали не скролва във вътрешен контейнер или е празна.")
        add_colors(secs, img, scale)
        text = page_text(page)
        result = dict(url=url, width=width, H=H, status=status, title=title, y0=raw["y0"], y1=raw["y1"], base_fs=raw["base_fs"], scroller=bool(sc),
                      capped=capped, max_height=max_height, scale=scale, notes=note, sections=secs,
                      console_errors=errors[:30], raw=raw)
        if save:
            os.makedirs(out_dir, exist_ok=True)
            png_path = os.path.join(out_dir, f"full_{width}.png")
            img.save(png_path)
            img.save(os.path.join(out_dir, f"full_{width}.jpg"), quality=80)
            open(os.path.join(out_dir, f"text_{width}.txt"), "w").write(text)
            result["png"] = png_path
            json.dump(result, open(os.path.join(out_dir, f"outline_{width}.json"), "w"), ensure_ascii=False, indent=1)
        result["_img"] = img
        result["_text"] = text
        return result
    finally:
        ctx.close()


def saved_original(dir_path, width):
    """Папка със запазен оригинал → (url, html, png) за ширината; None ако няма HTML."""
    html_path = None
    for cand in (f"page_{width}.html", "page.html"):
        p = os.path.join(dir_path, cand)
        if os.path.exists(p):
            html_path = p
            break
    png = None
    for cand in (f"full_{width}.png", f"stitched_{width}.png"):
        p = os.path.join(dir_path, cand)
        if os.path.exists(p):
            png = p
            break
    if not html_path:
        return None
    html = open(html_path, encoding="utf-8", errors="replace").read()
    m = (re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', html)
         or re.search(r'<meta[^>]+property=["\']og:url["\'][^>]*content=["\']([^"\']+)', html))
    url = m.group(1) if m else None
    if not url:
        for log in glob.glob(os.path.join(dir_path, "*.log")) + glob.glob(os.path.join(dir_path, "*.json")):
            mm = re.search(r"https?://[^\s\"']+", open(log, errors="replace").read())
            if mm:
                url = mm.group(0)
                break
    # скриптовете се махат: DOM-ът е вече рендериран, а JS би го пренаписал
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    return url, html, png


def capture(target, out_dir, widths=(390, 1440), max_height=DEFAULT_MAX_HEIGHT, keep_chrome=False, save=True):
    """URL или папка със запазен оригинал → {width: outline}."""
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # само headless
        try:
            for w in widths:
                if os.path.isdir(os.path.expanduser(target)):
                    d = os.path.expanduser(target)
                    ours = os.path.join(d, f"outline_{w}.json")
                    if os.path.exists(ours):
                        from PIL import Image
                        o = json.load(open(ours))
                        if o.get("raw"):  # секциите се смятат наново със сегашната логика
                            o["sections"] = build_sections(o["raw"])
                        o["_img"] = Image.open(o["png"]).convert("RGB") if o.get("png") and os.path.exists(o["png"]) else None
                        add_colors(o["sections"], o["_img"], o.get("scale", 1.0))
                        o["_text"] = open(os.path.join(d, f"text_{w}.txt")).read() if os.path.exists(os.path.join(d, f"text_{w}.txt")) else ""
                        res[w] = o
                        continue
                    so = saved_original(d, w)
                    if not so or not so[0]:
                        raise SystemExit(f"{d}: няма page_{w}.html с canonical адрес или outline_{w}.json")
                    url, html, png = so
                    res[w] = capture_one(browser, url, w, out_dir, max_height=max_height, keep_chrome=keep_chrome,
                                         html=html, src_png=png, save=save)
                    res[w]["source_dir"] = d
                else:
                    res[w] = capture_one(browser, target, w, out_dir, max_height=max_height, keep_chrome=keep_chrome, save=save)
        finally:
            browser.close()
    return res


def main():
    ap = argparse.ArgumentParser(description="Снимка + списък на секциите на страница (headless).")
    ap.add_argument("target", help="URL или папка със запазен оригинал")
    ap.add_argument("--out", required=True)
    ap.add_argument("--widths", default="390,1440")
    ap.add_argument("--max-height", type=int, default=DEFAULT_MAX_HEIGHT)
    ap.add_argument("--keep-chrome", action="store_true", help="не изрязвай хедъра/футъра на магазина")
    a = ap.parse_args()
    res = capture(a.target, a.out, widths=[int(x) for x in a.widths.split(",")], max_height=a.max_height, keep_chrome=a.keep_chrome)
    for w, o in res.items():
        print(f"{w}px: височина {o['H']} px, {len(o['sections'])} секции" + ("; " + "; ".join(o["notes"]) if o["notes"] else ""))
        for i, s in enumerate(o["sections"]):
            print(f"  {i + 1:2d}. y={s['y']:6d} h={s['h']:5d} {s['type']:8s} img={s['img'] + s['bgimg']} vid={s['video']} "
                  f"btn={s['button']} li={s['li']} rep={s['repeat']} | {s['heading'][:70]}")


if __name__ == "__main__":
    main()
