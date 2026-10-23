"""Рекламите от TrendTrack / Scrape Creators (competitor-ad-research на Вальо) → във формата на ads_all.json.

    python3 agent/adlib/import_playbook_ads.py <research>/ads.json --product kids --into runs/<x>/ads/ads_all.json [--today 2026-10-23] [--dry]

Вход: ads.json от agent/playbooks/research/digest.py ads (всяка реклама нормализирана: id, api TT/FB, advertiser,
page_id, days, countries, fmt, variants, title, body, link, media). Изход: записите се добавят към ads_all.json,
за да минат през скалата за сила на доказателствата заедно с Ad Library рекламите.
Дубликати: по meta_ad_id, после по (домейн на линка, първите 120 знака на текста).
И двата източника връщат само активни реклами (status=active / ACTIVE), затова active=true.
"""
import argparse, datetime, json, os, re, sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evidence import norm_url  # noqa: E402


def convert(a, product, today):
    days = a.get("days")
    first = str(today - datetime.timedelta(days=days)) if days is not None else None
    link = a.get("link") or ""
    clean, host = norm_url(link)
    fmt = (a.get("fmt") or "").lower()
    return dict(
        meta_ad_id=str(a.get("id")), collation_id=None, brand=a.get("advertiser"), page_id=a.get("page_id"),
        first_seen=first, days_running=days or 0, active=True,
        format="video" if "video" in fmt else ("carousel" if "carousel" in fmt or "dco" in fmt else "image"),
        headline=a.get("title") or "", primary_text=a.get("body") or "", transcript=a.get("transcript") or "",
        landing_url=link, landing_url_clean=clean or link, domain=host, duplicates=max(1, int(a.get("variants") or 1)),
        thumb=None, video=a.get("media") if "video" in fmt else None, media=a.get("media"), cta=a.get("cta"),
        countries=sorted(set(a.get("countries") or []) | set(a.get("searched") or [])),
        queries=a.get("problems") or [], product=product, source=f"playbooks:{a.get('api', '?')}",
    )


def key2(r):
    return (r.get("domain") or "", re.sub(r"\s+", " ", (r.get("primary_text") or "")[:120]).strip().lower())


def merge(existing, new):
    ids = {r.get("meta_ad_id") for r in existing}
    k2 = {key2(r) for r in existing if r.get("primary_text")}
    added = []
    for r in new:
        if r["meta_ad_id"] in ids or (r["primary_text"] and key2(r) in k2):
            continue
        ids.add(r["meta_ad_id"])
        k2.add(key2(r))
        added.append(r)
    return existing + added, added


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ads", help="ads.json от digest.py")
    ap.add_argument("--product", required=True, help="стойността на полето product (както в evidence_products на run.json)")
    ap.add_argument("--into", required=True, help="ads_all.json, към който се добавя")
    ap.add_argument("--today", help="дата на свалянето (по подразбиране днес)")
    ap.add_argument("--dry", action="store_true", help="само брои, не пише")
    a = ap.parse_args()
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    new = [convert(x, a.product, today) for x in json.load(open(a.ads)) if x.get("link")]
    into = os.path.expanduser(a.into)
    existing = json.load(open(into)) if os.path.exists(into) else []
    merged, added = merge(existing, new)
    print(f"в ads.json {len(new)} с линк · нови {len(added)} · дубликати {len(new) - len(added)} · общо {len(merged)}")
    if not a.dry:
        json.dump(merged, open(into, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
