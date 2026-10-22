"""Проверка на текста и техниката на страница: забранени думи, кирилица на RO, хоризонтален скрол, счупени снимки, JS грешки.

    python3 agent/qa/lint_copy.py <url | page.html> --client so_simple [--lang ro] [--scope ".dm"] [--json out.json]

Правилата са в agent/config/lint.json („common“ + клиента). Проверява видимия текст и alt/title на снимките
(„илюстративна снимка“ не може нито като надпис, нито като alt).
За URL отваря страницата headless на 390 px, скролва до дъното и проверява още:
  - хоризонтален скрол на 390 (и кои елементи излизат вдясно);
  - счупени снимки/видеа (naturalWidth 0, HTTP >= 400);
  - JS грешки в конзолата (своите отделно от външните скриптове).
Изходен код 1 при грешка от ниво error.
"""
import argparse, html as htmlmod, json, os, re, sys, time
from html.parser import HTMLParser
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CONFIG = os.path.join(HERE, "..", "config", "lint.json")
CYR = re.compile(r"[Ѐ-ӿ]")
CYR_RUN = re.compile(r"[\u0400-\u04FF]+(?:[\s,.]+[\u0400-\u04FF]+)*")
NEG = re.compile(r"(?:\bне|\bnu|\bnicht|\bnot)\s+$", re.I)


# ---------- чиста логика ----------

def load_rules(client, path=CONFIG):
    with open(path) as fh:
        cfg = json.load(fh)
    rules = list(cfg.get("common", []))
    if client:
        if client not in cfg:
            raise SystemExit(f"няма клиент {client} в {path}; има: " + ", ".join(k for k in cfg if not k.startswith("_") and k not in ("common", "console_ignore")))
        rules += cfg[client]["rules"]
    return rules


def context(text, a, b, pad=40):
    return re.sub(r"\s+", " ", text[max(0, a - pad):a] + "[" + text[a:b] + "]" + text[b:b + pad]).strip()


def lint_text(text, rules, lang=None, where="текст"):
    """Връща списък находки {rule, level, why, match, context, where}."""
    out, taken = [], []
    for r in rules:
        if r.get("lang") and r["lang"] != lang:  # правила само за един пазар (напр. лева на RO)
            continue
        for m in re.finditer(r["pattern"], text, flags=re.I):
            a, b = m.span()
            if any(a < tb and b > ta and tr == r.get("group", r["id"]) for ta, tb, tr in taken):
                continue
            taken.append((a, b, r.get("group", r["id"])))
            level = r["level"]
            note = ""
            if level == "error" and NEG.search(text[max(0, a - 6):a]):
                level, note = "warn", " (с отрицание, провери смисъла)"
            out.append(dict(rule=r["id"], level=level, why=r["why"] + note, match=m.group(0), context=context(text, a, b), where=where))
    if lang == "ro":
        for m in list(CYR_RUN.finditer(text))[:200]:
            out.append(dict(rule="cyrillic_on_ro", level="error", why="кирилица на RO страница", match=m.group(0),
                            context=context(text, m.start(), m.end(), 25), where=where))
    return out


def dedupe_cyr(findings, limit=20):
    """Кирилицата на RO: по една находка на контекст, до limit."""
    seen, out, n = set(), [], 0
    for f in findings:
        if f["rule"] == "cyrillic_on_ro":
            key = re.sub(r"\[|\]", "", f["context"])[:30]
            if key in seen:
                continue
            seen.add(key)
            n += 1
            if n > limit:
                continue
        out.append(f)
    return out


class _HTMLText(HTMLParser):
    SKIP = {"script", "style", "noscript", "template"}

    def __init__(self):
        super().__init__()
        self.parts, self.alts, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        a = dict(attrs)
        for k in ("alt", "title", "aria-label"):
            if a.get(k):
                self.alts.append(a[k])
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "section", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.parts.append(d)


def html_text(html):
    p = _HTMLText()
    p.feed(html)
    return htmlmod.unescape("".join(p.parts)), p.alts


# ---------- браузър ----------

PAGE_JS = r"""(scope) => {
  const root = (scope && document.querySelector(scope)) || document.querySelector('[data-qa-scroller]') || document.body;
  const W = document.documentElement.clientWidth;
  const sw = document.documentElement.scrollWidth;
  const over = [];
  if (sw > W + 1) {
    for (const e of document.querySelectorAll('body *')) {
      const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
      if (r.width < 1 || s.display === 'none' || s.visibility === 'hidden' || s.position === 'fixed') continue;
      if (r.right > W + 1 && ![...e.children].some(c => c.getBoundingClientRect().right > W + 1)) {
        over.push({tag: e.tagName.toLowerCase(), cls: String(e.className).slice(0, 60), right: Math.round(r.right),
                   y: Math.round(r.top + scrollY), text: (e.innerText || e.alt || '').trim().slice(0, 60)});
      }
      if (over.length >= 12) break;
    }
  }
  const broken = [];
  for (const i of root.querySelectorAll('img')) {
    const s = getComputedStyle(i); if (s.display === 'none') continue;
    const src = i.currentSrc || i.src || '';
    if (!src || src.startsWith('data:')) continue;
    if (i.complete && i.naturalWidth === 0) broken.push({tag: 'img', src: src.slice(0, 160), alt: i.alt, y: Math.round(i.getBoundingClientRect().top + scrollY)});
  }
  for (const v of root.querySelectorAll('video')) {
    if (v.error || v.networkState === 3) broken.push({tag: 'video', src: (v.currentSrc || v.src || (v.querySelector('source') || {}).src || '').slice(0, 160), y: Math.round(v.getBoundingClientRect().top + scrollY)});
  }
  const alts = [...root.querySelectorAll('img[alt], img[title], [aria-label]')].map(e => {
    const t = [e.getAttribute('alt'), e.getAttribute('title'), e.getAttribute('aria-label')].filter(Boolean).join(' | ');
    return t ? t + '  <' + e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/)[0] : '') + '>' : '';
  }).filter(Boolean);
  return {W, sw, over, broken, alts, text: root.innerText, imgs: root.querySelectorAll('img').length, videos: root.querySelectorAll('video').length};
}"""


def check_url(url, width=390, scope=None):
    from playwright.sync_api import sync_playwright
    from capture import open_page, lazy_scroll
    bad_http = []
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)  # само headless
        try:
            def hook(page):
                page.on("response", lambda r: bad_http.append({"status": r.status, "url": r.url[:160], "type": r.request.resource_type})
                        if r.status >= 400 and r.request.resource_type in ("image", "media", "font", "stylesheet", "script") else None)
            ctx, page, sc = open_page(b, url, width, errors=errors, on_page=hook)
            lazy_scroll(page, scroller=bool(sc))
            time.sleep(1.5)
            info = page.evaluate(PAGE_JS, scope)
            info["status"] = getattr(page, "qa_status", None)
            ctx.close()
        finally:
            b.close()
    host = urlparse(url).netloc
    ignore = json.load(open(CONFIG)).get("console_ignore", {}).get("patterns", [])
    own, ext = [], []
    for e in errors:
        h = urlparse(e.get("url") or "").netloc
        noise = any(re.search(p, (e.get("url") or "") + " " + e["text"], re.I) for p in ignore)
        (own if (not noise and (not h or h == host or "cdn.shopify.com" in h)) else ext).append(e)
    info["errors_own"], info["errors_external"] = own, ext
    info["bad_http"] = bad_http
    return info


def lint(target, client, lang=None, scope=None, width=390, config=CONFIG):
    rules = load_rules(client, config)
    res = dict(target=target, client=client, lang=lang)
    if os.path.exists(os.path.expanduser(target)):
        text, alts = html_text(open(os.path.expanduser(target), encoding="utf-8", errors="replace").read())
        res["checked"] = "само текст (HTML файл, без браузър)"
        tech = None
    else:
        tech = check_url(target, width=width, scope=scope)
        text, alts = tech["text"], tech["alts"]
        res["checked"] = f"страница на {width} px (headless)"
    f = lint_text(text, rules, lang) + lint_text("\n".join(alts), rules, lang, where="alt/title")
    f = dedupe_cyr(f)
    if tech:
        if tech.get("status") and tech["status"] >= 400:
            f.append(dict(rule="http_status", level="error", why=f"страницата връща HTTP {tech['status']}", match="", context="", where="page"))
        if tech["sw"] > tech["W"] + 1:
            f.append(dict(rule="overflow_x", level="error", why=f"хоризонтален скрол на {width}: ширина {tech['sw']} > {tech['W']}",
                          match="", context="; ".join(f"{o['tag']}.{o['cls'][:30]} до {o['right']}px y={o['y']} „{o['text'][:30]}“" for o in tech["over"][:6]),
                          where="layout"))
        for x in tech["broken"]:
            f.append(dict(rule="broken_media", level="error", why=f"счупен {x['tag']}", match=x["src"], context=f"y={x['y']} {x.get('alt', '')}", where="media"))
        for x in tech["bad_http"]:
            if x["type"] in ("image", "media"):
                f.append(dict(rule="http_error", level="error", why=f"HTTP {x['status']} за {x['type']}", match=x["url"], context="", where="media"))
        for e in tech["errors_own"]:
            f.append(dict(rule="js_error", level="error", why="JS грешка", match=e["text"][:160], context=e.get("url", ""), where="console"))
        for e in tech["errors_external"]:
            f.append(dict(rule="js_error_external", level="warn", why="JS грешка от външен скрипт", match=e["text"][:160], context=e.get("url", ""), where="console"))
        res["stats"] = dict(width=width, scroll_width=tech["sw"], imgs=tech["imgs"], videos=tech["videos"], text_chars=len(text))
    res["findings"] = f
    res["errors"] = sum(1 for x in f if x["level"] == "error")
    res["warnings"] = sum(1 for x in f if x["level"] == "warn")
    return res


def text_report(res):
    L = [f"Копи и техника ({res['checked']}): {res['errors']} грешки, {res['warnings']} за проверка"]
    for x in res["findings"]:
        mark = "!!" if x["level"] == "error" else "??"
        L.append(f"  {mark} [{x['rule']}] {x['why']}: „{x['match'][:60]}“ {('… ' + x['context']) if x['context'] else ''} ({x['where']})")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Забранени думи + техническа проверка на страница.")
    ap.add_argument("target", help="URL или HTML файл")
    ap.add_argument("--client", default="so_simple")
    ap.add_argument("--lang", default=None, help="ro → всяка кирилска буква е грешка")
    ap.add_argument("--scope", default=None, help="CSS селектор на съдържанието (по подразбиране цялото body)")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    res = lint(a.target, a.client, lang=a.lang, scope=a.scope, width=a.width)
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    print(text_report(res))
    sys.exit(1 if res["errors"] else 0)


if __name__ == "__main__":
    main()
