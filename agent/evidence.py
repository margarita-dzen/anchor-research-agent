"""Скала „сила на доказателствата“: кои лендинги от Meta Ad Library реално работят.

Вход: ads_all.json (формата на consolidate.py: по един запис на collation група).
Изход: JSON с минали/отпаднали URL-и, оценка 0-100 и разбивка по сигнали.

    python3 agent/evidence.py ads_all.json --product acne --product herbal \
        --traffic traffic.json [--resolved resolved.json] --out landing_evidence_acne.json

Нива:
  1. Задължителни условия (gate): истински лендинг, не соц. мрежа/маркетплейс/аптечна марка/начална страница,
     >= 3 реклами или 1 реклама с >= 5 дубликата, поне 1 активна.
  2. Сила 0-100: активни 25, дубликати 20, нови за 30 дни 20, макс. дни 15, държави 10, трафик на домейна 10.
     Липсващ трафик не наказва: теглото му се разпределя върху останалите сигнали.
"""
import argparse, collections, datetime, json, math, os
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

# сигнал: (тегло, таван, мащаб). log = log1p(x)/log1p(таван); lin = x/таван; и двете до 1.
SIGNALS = {
    "active_ads": (25, 50, "log"),
    "duplicates": (20, 100, "log"),
    "new_ads_30d": (20, 20, "log"),
    "max_days": (15, 365, "lin"),
    "countries": (10, 6, "log"),
    "domain_visits": (10, 1_000_000, "log"),
}
GATE = dict(min_ads=3, min_dups_single=5, min_active=1)
NEW_WINDOW_DAYS = 30


def load_blocklist(path=None):
    b = json.load(open(path or os.path.join(HERE, "config", "blocklist.json")))
    return {k: [d.lower() for d in v] for k, v in b.items() if not k.startswith("_")}


def norm_url(u):
    p = urlparse((u or "").strip())
    if not p.netloc:
        return "", ""
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    return f"https://{host}{path}", host


def blocked(host, blocklist):
    for kind, domains in blocklist.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return kind
    return None


def load_traffic(path):
    """{domain: visits} от dict, от списък [{domain, visits|monthly_visits}] или от funnels_*.json. 0 = неизвестно."""
    if not path:
        return {}
    data = json.load(open(path))
    if isinstance(data, dict):
        rows = [{"domain": k, "visits": v} for k, v in data.items()]
    else:
        rows = data
    out = {}
    for r in rows:
        d = (r.get("domain") or "").lower().removeprefix("www.")
        v = r.get("visits", r.get("monthly_visits"))
        if d and v:
            out[d] = max(out.get(d, 0), int(v))
    return out


def scale(x, cap, kind):
    if x is None:
        return None
    x = max(0, x)
    v = math.log1p(x) / math.log1p(cap) if kind == "log" else x / cap
    return min(1.0, v)


def evidence_score(signals):
    """signals: {име: стойност или None}. Връща (оценка 0-100, разбивка)."""
    parts, wsum = {}, 0
    for name, (w, cap, kind) in SIGNALS.items():
        s = scale(signals.get(name), cap, kind)
        if s is None:
            continue
        parts[name] = (w, s)
        wsum += w
    if not wsum:
        return 0.0, {}
    breakdown = {n: round(100 * w * s / wsum, 1) for n, (w, s) in parts.items()}
    return round(sum(breakdown.values()), 1), breakdown


def aggregate(ads, today, products=None, traffic=None, blocklist=None, resolved=None):
    """resolved: {landing_url: краен URL} от agent/adlib/resolve_urls.py (по желание)."""
    blocklist = blocklist if blocklist is not None else load_blocklist()
    traffic = traffic or {}
    resolved = resolved or {}
    groups = collections.defaultdict(lambda: dict(ads=0, active_ads=0, duplicates=0, new_ads_30d=0, max_days=0,
                                                  countries=set(), brands=set(), ad_ids=[], host=""))
    for a in ads:
        if products and a.get("product") not in products:
            continue
        url, host = norm_url(resolved.get(a.get("landing_url")) or resolved.get(a.get("landing_url_clean"))
                             or a.get("landing_url_clean") or a.get("landing_url"))
        g = groups[url]
        g["host"] = host
        g["ads"] += 1
        g["active_ads"] += bool(a.get("active"))
        g["duplicates"] += a.get("duplicates") or 1
        g["max_days"] = max(g["max_days"], a.get("days_running") or 0)
        g["countries"] |= set(a.get("countries") or [])
        if a.get("brand"):
            g["brands"].add(a["brand"])
        g["ad_ids"].append(a.get("meta_ad_id"))
        fs = a.get("first_seen")
        if fs and (today - datetime.date.fromisoformat(fs)).days <= NEW_WINDOW_DAYS:
            g["new_ads_30d"] += 1

    passed, rejected = [], []
    for url, g in groups.items():
        host = g["host"]
        row = dict(url=url, domain=host, brands=sorted(g["brands"]), ads=g["ads"], active_ads=g["active_ads"],
                   duplicates=g["duplicates"], new_ads_30d=g["new_ads_30d"], max_days=g["max_days"],
                   countries=sorted(g["countries"]), domain_visits=traffic.get(host), ad_ids=g["ad_ids"][:20])
        reasons = []
        if not url:
            reasons.append("няма линк")
        else:
            kind = blocked(host, blocklist)
            if kind:
                reasons.append(f"блокиран домейн ({kind})")
            if urlparse(url).path == "/":
                reasons.append("начална страница")
        if not (g["ads"] >= GATE["min_ads"] or g["duplicates"] >= GATE["min_dups_single"]):
            reasons.append(f"под {GATE['min_ads']} реклами и под {GATE['min_dups_single']} дубликата")
        if g["active_ads"] < GATE["min_active"]:
            reasons.append("няма активна реклама")
        if reasons:
            row["rejected"] = reasons
            rejected.append(row)
            continue
        sig = {k: row[k] for k in SIGNALS if k != "countries"}
        sig["countries"] = len(row["countries"])
        row["evidence"], row["evidence_breakdown"] = evidence_score(sig)
        passed.append(row)
    passed.sort(key=lambda r: -r["evidence"])
    rejected.sort(key=lambda r: -(r["ads"] + r["duplicates"]))
    return passed, rejected


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ads")
    ap.add_argument("--product", action="append", help="филтър по полето product (може няколко пъти)")
    ap.add_argument("--traffic", help="JSON с трафик по домейн (TrendTrack lookup)")
    ap.add_argument("--today", help="дата на свалянето YYYY-MM-DD (по подразбиране: най-новият first_seen)")
    ap.add_argument("--blocklist")
    ap.add_argument("--resolved", help="resolved.json от agent/adlib/resolve_urls.py: крайни URL-и без проследяване")
    ap.add_argument("--out")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    ads = json.load(open(a.ads))
    today = datetime.date.fromisoformat(a.today) if a.today else max(
        datetime.date.fromisoformat(x["first_seen"]) for x in ads if x.get("first_seen"))
    passed, rejected = aggregate(ads, today, set(a.product or []) or None, load_traffic(a.traffic), load_blocklist(a.blocklist),
                                 json.load(open(a.resolved)) if a.resolved else None)
    if a.out:
        json.dump(dict(scale="evidence-v1", today=str(today), weights={k: v[0] for k, v in SIGNALS.items()}, gate=GATE,
                       passed=passed, rejected=rejected), open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"дата {today} · минават {len(passed)} · отпадат {len(rejected)}")
    print(f"{'сила':>5} {'акт':>4} {'дуб':>4} {'нови':>4} {'дни':>4} {'държ':>4} {'трафик':>8}  url")
    for r in passed[:a.top]:
        v = r["domain_visits"]
        print(f"{r['evidence']:5.1f} {r['active_ads']:4} {r['duplicates']:4} {r['new_ads_30d']:4} {r['max_days']:4} "
              f"{len(r['countries']):4} {v if v else '-':>8}  {r['url'][:80]}")


if __name__ == "__main__":
    main()
