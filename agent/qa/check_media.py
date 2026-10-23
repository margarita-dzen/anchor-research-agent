"""Проверка на снимките на страница (absolute-clone.md §8.3): повторения, завъртени снимки, изрязани миниатюри, текст върху продукта.

    python3 agent/qa/check_media.py <url> [--widths 390,1440] [--product "acne|мехлем|стик"] [--json out.json]

Отваря страницата headless (никога видим браузър) на всяка ширина, скролва, за да заредят lazy снимките, и дава:
  - ГРЕШКА: една и съща снимка повече от веднъж (Shopify CDN адресите се нормализират: без query, без _<W>x<H>);
    иконки < MIN_PX, data: URI и клонинги на слайдери (вътре в aria-hidden="true", .slick-cloned, .swiper-slide-duplicate) не се броят;
  - ГРЕШКА: снимка, показана легнала, а е портрет (или обратно) с голяма разлика в пропорциите (вероятно завъртяна);
  - ЗА ПРОВЕРКА: object-fit:cover в кутия <= THUMB_PX, когато пропорциите се различават > CROP_RATIO пъти (изрязана бутилка/подарък);
  - ЗА ПРОВЕРКА: текст върху снимка, чийто alt споменава продукта.
Изходен код 1 при грешка.
"""
import argparse, json, os, re, sys, time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MIN_PX = 60
ROT_RATIO = 1.6
ROT_MIN_PX = 120
THUMB_PX = 80
CROP_RATIO = 1.6
PRODUCT_DEFAULT = r"acne|мехлем|стик|балсам|крем|серум|продукт|product|so simple|sos\b|gone|bundle|комплект|опаковк"
SIZE_SUFFIX = re.compile(r"_(?:\d+x\d*|x\d+|\d+x)(?:@\d+x)?(?:_crop_\w+)?(?=\.\w+$)", re.I)


# ---------- чиста логика ----------

def norm_url(u):
    """Ключ за сравнение: без протокол и query (width/v се игнорират), без _<W>x<H> и @2x преди разширението."""
    if not u or u.startswith("data:"):
        return None
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    p = urlparse(u)
    path = SIZE_SUFFIX.sub("", p.path)
    path = re.sub(r"@\d+x(?=\.\w+$)", "", path)
    return (p.netloc.lower() + path).rstrip("/")


def countable(im):
    """Снимки, които се броят за повторения: видими, не иконки, не клонинги на слайдер."""
    if im.get("clone") or not norm_url(im.get("src")):
        return False
    return max(im.get("w", 0), im.get("h", 0)) >= MIN_PX and min(im.get("w", 0), im.get("h", 0)) > 0


def duplicates(images):
    """images = [{src, w, h, y, alt, clone}]. Връща [{key, count, items}] за снимките, ползвани повече от веднъж."""
    by = {}
    for im in images:
        if countable(im):
            by.setdefault(norm_url(im["src"]), []).append(im)
    return [dict(key=k, count=len(v), items=v) for k, v in by.items() if len(v) > 1]


def aspect(w, h):
    return w / h if w and h else None


def rotated(im):
    """Показана легнала, а е портрет (или обратно), с разлика в пропорциите >= ROT_RATIO."""
    ra, na = aspect(im.get("w"), im.get("h")), aspect(im.get("nw"), im.get("nh"))
    if not ra or not na or im.get("clone") or min(im["w"], im["h"]) < ROT_MIN_PX:
        return False
    if (ra > 1) == (na > 1) or abs(ra - 1) < 0.1 or abs(na - 1) < 0.1:
        return False
    return max(ra / na, na / ra) >= ROT_RATIO


def cropped_thumb(im):
    """object-fit:cover в малка кутия, когато пропорциите на снимката и кутията се различават > CROP_RATIO."""
    ra, na = aspect(im.get("w"), im.get("h")), aspect(im.get("nw"), im.get("nh"))
    if not ra or not na or im.get("fit") != "cover" or max(im["w"], im["h"]) > THUMB_PX:
        return False
    return max(ra / na, na / ra) > CROP_RATIO


PAGE_JS = r"""(prod) => {
  const re = new RegExp(prod, 'i');
  const isClone = e => !!e.closest('[aria-hidden="true"], .slick-cloned, .swiper-slide-duplicate, [data-clone], .is-clone, .cloned');
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05 && r.width > 0 && r.height > 0; };
  const imgs = [];
  for (const i of document.querySelectorAll('img')) {
    if (!vis(i)) continue;
    const r = i.getBoundingClientRect();
    imgs.push({src: i.currentSrc || i.src || i.getAttribute('data-src') || '', w: Math.round(r.width), h: Math.round(r.height),
      nw: i.naturalWidth, nh: i.naturalHeight, x: Math.round(r.left), y: Math.round(r.top + scrollY), alt: (i.alt || '').slice(0, 80),
      fit: getComputedStyle(i).objectFit, clone: isClone(i), product: re.test(i.alt || '')});
  }
  const over = [];
  const prodImgs = [...document.querySelectorAll('img')].filter(i => vis(i) && re.test(i.alt || '') && !isClone(i));
  if (prodImgs.length) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const seen = new Set();
    while (walker.nextNode()) {
      const t = walker.currentNode; const el = t.parentElement;
      if (!el || seen.has(el) || t.textContent.trim().length < 3 || !vis(el) || isClone(el)) continue;
      if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'OPTION'].includes(el.tagName)) continue;
      seen.add(el);
      const rg = document.createRange(); rg.selectNodeContents(t); const tr = rg.getBoundingClientRect();
      if (!tr.width || !tr.height) continue;
      for (const im of prodImgs) {
        const ir = im.getBoundingClientRect();
        const ix = Math.max(0, Math.min(tr.right, ir.right) - Math.max(tr.left, ir.left));
        const iy = Math.max(0, Math.min(tr.bottom, ir.bottom) - Math.max(tr.top, ir.top));
        if (ix * iy > 0.3 * tr.width * tr.height && ir.width >= 120) {
          over.push({text: t.textContent.trim().slice(0, 60), alt: im.alt.slice(0, 60), y: Math.round(ir.top + scrollY)});
          break;
        }
      }
    }
  }
  return {imgs, over: over.slice(0, 30)};
}"""


def analyze(info, width):
    """Сурови данни от страницата → находки {level, kind, width, msg, ...}."""
    out = []
    for d in duplicates(info["imgs"]):
        ys = ", ".join(str(i["y"]) for i in d["items"][:6])
        out.append(dict(level="error", kind="duplicate", width=width, key=d["key"], count=d["count"],
                        msg=f"{width}px: снимката {d['key'].split('/')[-1][:60]} е ползвана {d['count']} пъти (y={ys}), alt „{d['items'][0]['alt'][:40]}“"))
    for im in info["imgs"]:
        if rotated(im):
            out.append(dict(level="error", kind="rotation", width=width, src=im["src"][:160],
                            msg=f"{width}px: вероятно завъртяна: показана {im['w']}x{im['h']}, файлът е {im['nw']}x{im['nh']} (y={im['y']}, alt „{im['alt'][:40]}“)"))
        if cropped_thumb(im):
            out.append(dict(level="warn", kind="crop", width=width, src=im["src"][:160],
                            msg=f"{width}px: миниатюра с object-fit:cover {im['w']}x{im['h']}, файлът е {im['nw']}x{im['nh']}: продуктът се реже, сложи contain (y={im['y']}, alt „{im['alt'][:40]}“)"))
    by = {}
    for o in info.get("over", []):  # по един ред на снимка
        by.setdefault((o["alt"], o["y"]), []).append(o["text"])
    for (alt, y), texts in by.items():
        out.append(dict(level="warn", kind="overlap", width=width,
                        msg=f"{width}px: {len(texts)} текста върху продукта „{alt}“ (y={y}): " + " / ".join(f"„{t[:30]}“" for t in texts[:4])))
    return out


# ---------- браузър ----------

def check(url, widths=(390, 1440), product=PRODUCT_DEFAULT):
    from playwright.sync_api import sync_playwright
    from capture import open_page, lazy_scroll
    findings, counts = [], {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)  # само headless
        try:
            for w in widths:
                ctx, page, sc = open_page(b, url, w)
                lazy_scroll(page, scroller=bool(sc))
                time.sleep(1.0)
                info = page.evaluate(PAGE_JS, product)
                counts[w] = len(info["imgs"])
                findings += analyze(info, w)
                ctx.close()
        finally:
            b.close()
    errors = sum(f["level"] == "error" for f in findings)
    return dict(url=url, widths=list(widths), images=counts, findings=findings, errors=errors,
                warnings=len(findings) - errors)


def text_report(res):
    L = [f"Снимки: {', '.join(f'{w}px {n}' for w, n in res['images'].items())}; {res['errors']} грешки, {res['warnings']} за проверка"]
    for f in res["findings"]:
        L.append(("ГРЕШКА  " if f["level"] == "error" else "ПРОВЕРИ ") + f["msg"])
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Снимките на страница: повторения, завъртане, изрязване, текст върху продукта")
    ap.add_argument("url")
    ap.add_argument("--widths", default="390,1440")
    ap.add_argument("--product", default=PRODUCT_DEFAULT, help="regex за alt на продуктовите снимки")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    res = check(a.url, [int(x) for x in a.widths.split(",")], a.product)
    print(text_report(res))
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    sys.exit(1 if res["errors"] else 0)


if __name__ == "__main__":
    main()
