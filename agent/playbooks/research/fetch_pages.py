#!/usr/bin/env python3
"""Fetch competitor landing pages as plain text plus a list of funnel signals (free, no API).

Reads URLs from landing-targets.json (made by digest.py), from a text file with "name url" per line,
or from the command line. For each page it saves pages/<name>.txt with:
  final URL, HTTP status, title, meta description, headings (H1 to H3), buttons and links,
  form fields, prices found, signal flags (guarantee, cash on delivery, free shipping, reviews,
  countdown, scarcity, bundles, subscription), shop platform, and the full visible text.

  python3 fetch_pages.py --targets landing-targets.json --top 15
  python3 fetch_pages.py --list urls.txt
  python3 fetch_pages.py https://competitor.com/products/x https://other.com/lp

It does NOT run JavaScript, so tracking pixels never fire. Pages built in JavaScript come back
almost empty; those are marked LOW TEXT. Open them in a real browser instead (Playwright MCP),
with facebook.net / connect.facebook.net blocked, and save a text snapshot by hand.
Standard library only.
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

# Words that signal each funnel element, in the languages the team works in most.
SIGNALS = {
    "guarantee": r"money.?back|geld.?zur[uü]ck|rembours|satisfait ou|garanci|garanț|garantie|гаранци|върнем парите|"
                 r"zwrot pieni|vrácení peněz|pénzvisszafizet|days? risk.?free|risk.?free|bez riziko",
    "cash_on_delivery": r"cash on delivery|\bCOD\b|наложен платеж|наложен|ramburs|plata la livrare|dobírk|dobierk|"
                        r"utánvét|za pobraniem|przy odbiorze|nachnahme|contre.?remboursement|pago contra",
    "free_shipping": r"free (shipping|delivery)|kostenlose?r? versand|livraison gratuite|безплатна доставка|"
                     r"livrare gratuit|darmowa dostawa|doprava zdarma|ingyenes szállítás",
    "reviews": r"trustpilot|judge\.me|reviews?\b|bewertung|avis|отзив|recenz|vélemény|értékelés|opini|★",
    "countdown": r"countdown|timer|\d{1,2}:\d{2}:\d{2}|offer ends|endet in|expire|изтича|se termină|kończy się",
    "scarcity": r"only \d+ left|nur noch \d+|plus que \d+|остават само|ultimele|ostatnie \d+|posledn|limited stock|"
                r"sold out|ausverkauft|изчерпан",
    "bundle": r"buy \d|\d\s?\+\s?\d|\b2x\b|\b3x\b|2er|duo|family pack|bundle|комплект|пакет|pachet|zestaw|sada|csomag",
    "subscription": r"subscribe|subscription|abo\b|abonnement|абонамент|abonament|předplatn|előfizet",
    "doctor_or_expert": r"dermatolog|dentist|zahnarzt|doctor|dr\.|лекар|доктор|medic|lekarz|lékař|orvos|expert",
    "study_claim": r"stud(y|ie)|clinical|klinisch|clinique|клинич|проучване|studiu|badani|studie|tanulmány|harvard",
}
PRICE = re.compile(r"(?:€|EUR|лв\.?|BGN|lei|RON|zł|PLN|Kč|CZK|Ft|HUF|£|\$|CHF|kr\.?|SEK|DKK|NOK)\s?\d[\d.,]*"
                   r"|\d[\d.,]*\s?(?:€|EUR|лв\.?|BGN|lei|RON|zł|PLN|Kč|CZK|Ft|HUF|£|CHF|kr\.?|SEK|DKK|NOK)\b", re.I)
PLATFORMS = {
    "Shopify": r"cdn\.shopify\.com|Shopify\.theme", "WooCommerce": r"woocommerce|wp-content",
    "ClickFunnels": r"clickfunnels", "GoHighLevel": r"leadconnectorhq|msgsndr", "Funnelish": r"funnelish",
    "Webflow": r"webflow", "Wix": r"wix\.com|wixstatic", "Next.js": r"__NEXT_DATA__",
}
TRACKERS = {"Meta pixel": r"fbq\(|connect\.facebook\.net", "Google": r"gtag\(|googletagmanager",
            "TikTok pixel": r"analytics\.tiktok\.com|ttq\.", "Clarity": r"clarity\.ms", "Hotjar": r"hotjar"}


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.text, self.heads, self.links, self.fields = [], [], [], []
        self.cur_head = None
        self.cur_link = None
        self.title = ""
        self.in_title = False
        self.meta_desc = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg", "template"):
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "meta" and (a.get("name") or "").lower() == "description":
            self.meta_desc = a.get("content") or ""
        elif tag in ("h1", "h2", "h3"):
            self.cur_head = [tag, ""]
        elif tag in ("a", "button"):
            self.cur_link = ["", a.get("href") or ""]
        elif tag in ("input", "select", "textarea"):
            if (a.get("type") or "") not in ("hidden",):
                self.fields.append(a.get("name") or a.get("placeholder") or a.get("type") or tag)
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr", "section"):
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "template") and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        elif tag in ("h1", "h2", "h3") and self.cur_head:
            t = " ".join(self.cur_head[1].split())
            if t:
                self.heads.append(f"{self.cur_head[0].upper()}: {t}")
            self.cur_head = None
        if tag in ("a", "button", "span", "label", "td"):
            self.text.append(" ")
        if tag in ("a", "button") and self.cur_link:
            t = " ".join(self.cur_link[0].split())
            if t:
                self.links.append(f"{t[:60]} -> {self.cur_link[1]}")
            self.cur_link = None

    def handle_data(self, d):
        if self.skip:
            return
        if self.in_title:
            self.title += d
        if self.cur_head:
            self.cur_head[1] += d
        if self.cur_link:
            self.cur_link[0] += d
        self.text.append(d)


def fetch(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,de;q=0.8,bg;q=0.7"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            cs = r.headers.get_content_charset() or "utf-8"
            return r.status, r.geturl(), raw.decode(cs, "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, e.read().decode("utf-8", "replace")


def analyse(name, url, status, final, page):
    p = Extract()
    try:
        p.feed(page)
    except Exception as e:  # malformed HTML; keep what we have
        print(f"  parse warning {name}: {e}", file=sys.stderr)
    text = re.sub(r"[ \t]+", " ", "".join(p.text))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    flags = {k: sorted({m.group(0).strip()[:30] for m in re.finditer(v, text, re.I)})[:6] for k, v in SIGNALS.items()}
    prices = sorted({m.group(0).strip().rstrip(".,") for m in PRICE.finditer(text)})[:25]
    plat = [k for k, v in PLATFORMS.items() if re.search(v, page, re.I)]
    trk = [k for k, v in TRACKERS.items() if re.search(v, page, re.I)]
    low = len(text) < 800
    lines = [
        f"NAME: {name}", f"URL: {url}", f"FINAL URL: {final}", f"HTTP: {status}",
        f"TITLE: {html.unescape(p.title.strip())}", f"META: {p.meta_desc}",
        f"PLATFORM: {', '.join(plat) or '?'} | TRACKERS: {', '.join(trk) or '-'}",
        f"TEXT LENGTH: {len(text)}" + ("  LOW TEXT: probably built in JavaScript, open it in a browser" if low else ""),
        f"PRICES SEEN: {', '.join(prices) or '-'}",
        "SIGNALS (word matches, verify on the page):",
    ] + [f"  {k}: {', '.join(v) if v else '-'}" for k, v in flags.items()] + [
        f"FORM FIELDS: {', '.join(p.fields[:40]) or '-'}",
        "", "=== HEADINGS", *p.heads[:80],
        "", "=== BUTTONS AND LINKS (first 80)", *list(dict.fromkeys(p.links))[:80],
        "", "=== VISIBLE TEXT", text,
    ]
    return "\n".join(lines), low


def slug(s):
    return re.sub(r"[^\w\-]+", "-", s.lower()).strip("-")[:60] or "page"


def main():
    ap = argparse.ArgumentParser(description="Fetch landing pages as text + funnel signals (free).",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="URLs to fetch")
    ap.add_argument("--targets", help="landing-targets.json from digest.py")
    ap.add_argument("--top", type=int, default=15, help="how many targets to take (default 15)")
    ap.add_argument("--skip", help="regex on URL/advertiser to skip (e.g. clinics, pet products)")
    ap.add_argument("--list", help="text file with 'name url' per line")
    ap.add_argument("--out", default="pages", help="output folder (default ./pages)")
    ap.add_argument("--refresh", action="store_true", help="fetch again even if the .txt exists")
    ap.add_argument("--timeout", type=int, default=30)
    a = ap.parse_args()

    jobs = []
    if a.targets:
        with open(a.targets, encoding="utf-8") as fh:
            rows = json.load(fh)
        skip = re.compile(a.skip, re.I) if a.skip else None
        for r in rows:
            if skip and skip.search(f"{r.get('url')} {r.get('advertiser')}"):
                continue
            jobs.append((slug(f"{r.get('domain', '')}-{r.get('oldest_days', '')}d"), r["url"]))
            if len(jobs) >= a.top:
                break
    if a.list:
        with open(a.list, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2:
                    jobs.append((slug(parts[0]), parts[1]))
    for u in a.urls:
        jobs.append((slug(re.sub(r"^https?://(www\.)?", "", u)), u))
    if not jobs:
        ap.print_help()
        return

    os.makedirs(a.out, exist_ok=True)
    for name, url in jobs:
        path = os.path.join(a.out, name + ".txt")
        if os.path.exists(path) and not a.refresh:
            print(f"cached  {name}")
            continue
        try:
            status, final, page = fetch(url, a.timeout)
        except Exception as e:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"URL: {url}\nERROR: {e}\n")
            print(f"ERROR   {name}: {e}")
            continue
        report, low = analyse(name, url, status, final, page)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"{status}     {name}  {'LOW TEXT, use a browser' if low else ''}")


if __name__ == "__main__":
    main()
