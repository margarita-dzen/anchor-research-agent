"""Учене от собствените резултати: разход, покупки и ROAS по фуния, ъгъл, концепция и автор на копито.

    python3 agent/results.py --account act_2897573163607813 --since 2026-10-01 --until 2026-10-22 \
        --match atopi --out results_atopi.json

Как разпознава какво е какво (без ръчно маркиране):
  - лендинг   = пътят на линка в креатива (object_story_spec / asset_feed_spec), напр. /pages/atopichna-kozha
  - кампания  = utm_campaign от url_tags или линка (напр. atopi_adv_oct26)
  - концепция = utm_content (напр. c07 или at07-ogilvy); суфиксът след последното „-“ е авторът от copy-masters, ако е
                един от schwartz|ogilvy|hormozi|sugarman|caples
Покупка = само action_type "omni_purchase" (insights брои една покупка 3 пъти под различни имена).
Токенът: META_TOKEN от средата или Token 2 от ~/.claude/projects/-Users-magi/memory/reference_meta_token.md.
Само четене, нищо не се променя в акаунта.
"""
import argparse, collections, json, os, re, urllib.parse, urllib.request

API = "https://graph.facebook.com/v21.0"
AUTHORS = {"schwartz", "ogilvy", "hormozi", "sugarman", "caples"}
PURCHASE = "omni_purchase"


def token():
    if os.environ.get("META_TOKEN"):
        return os.environ["META_TOKEN"]
    p = os.path.expanduser("~/.claude/projects/-Users-magi/memory/reference_meta_token.md")
    toks = re.findall(r"EAA[A-Za-z0-9]{50,}", open(p).read())
    return toks[1] if len(toks) > 1 else toks[0]


def get_all(url):
    out = []
    while url:
        d = json.load(urllib.request.urlopen(url, timeout=60))
        if "error" in d:
            raise SystemExit(d["error"])
        out += d.get("data", [])
        url = (d.get("paging") or {}).get("next")
    return out


def creative_link(c):
    oss = c.get("object_story_spec") or {}
    for k in ("link_data", "video_data", "photo_data"):
        x = oss.get(k) or {}
        link = x.get("link") or ((x.get("call_to_action") or {}).get("value") or {}).get("link")
        if link:
            return link
    for lu in (c.get("asset_feed_spec") or {}).get("link_urls") or []:
        if lu.get("website_url"):
            return lu["website_url"]
    return ""


def utm(link, tags):
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(link).query))
    q.update(dict(urllib.parse.parse_qsl(tags or "")))
    return q


def num(actions, kind):
    for a in actions or []:
        if a.get("action_type") == kind:
            return float(a.get("value") or 0)
    return 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--match", help="регулярен израз върху лендинг/кампания/име на реклама, за да се ограничи изходът")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    T = token()
    tr = urllib.parse.quote(json.dumps({"since": a.since, "until": a.until}))
    ins = get_all(f"{API}/{a.account}/insights?level=ad&time_range={tr}&limit=500"
                  f"&fields=ad_id,ad_name,campaign_name,adset_name,spend,impressions,clicks,actions,action_values&access_token={T}")
    ads = {}
    ids = [r["ad_id"] for r in ins]
    for i in range(0, len(ids), 50):
        chunk = ",".join(ids[i:i + 50])
        d = json.load(urllib.request.urlopen(f"{API}/?ids={chunk}&fields=id,name,creative{{url_tags,object_story_spec,asset_feed_spec}}&access_token={T}", timeout=60))
        ads.update(d)
    rx = re.compile(a.match, re.I) if a.match else None
    rows = []
    for r in ins:
        c = (ads.get(r["ad_id"]) or {}).get("creative") or {}
        link = creative_link(c)
        q = utm(link, c.get("url_tags"))
        path = urllib.parse.urlparse(link).path or "?"
        content = q.get("utm_content", "")
        author = content.rsplit("-", 1)[-1].lower() if "-" in content and content.rsplit("-", 1)[-1].lower() in AUTHORS else None
        row = dict(ad_id=r["ad_id"], ad_name=r.get("ad_name"), campaign=r.get("campaign_name"), landing=path,
                   utm_campaign=q.get("utm_campaign"), concept=content or None, author=author,
                   spend=float(r.get("spend") or 0), purchases=num(r.get("actions"), PURCHASE),
                   revenue=num(r.get("action_values"), PURCHASE), clicks=int(r.get("clicks") or 0))
        if rx and not rx.search(" ".join(str(row[k] or "") for k in ("landing", "utm_campaign", "ad_name", "campaign"))):
            continue
        rows.append(row)

    def group(key):
        g = collections.defaultdict(lambda: dict(spend=0.0, purchases=0.0, revenue=0.0, ads=0))
        for r in rows:
            k = r[key] or "—"
            for f in ("spend", "purchases", "revenue"):
                g[k][f] += r[f]
            g[k]["ads"] += 1
        out = []
        for k, v in g.items():
            v = {f: round(x, 2) for f, x in v.items()}
            v["roas"] = round(v["revenue"] / v["spend"], 2) if v["spend"] else None
            v["cpa"] = round(v["spend"] / v["purchases"], 2) if v["purchases"] else None
            out.append(dict(key=k, **v))
        return sorted(out, key=lambda x: -x["spend"])

    report = dict(account=a.account, since=a.since, until=a.until, ads=rows,
                  by_landing=group("landing"), by_campaign=group("utm_campaign"), by_concept=group("concept"), by_author=group("author"))
    json.dump(report, open(a.out, "w"), ensure_ascii=False, indent=1)
    for name in ("by_landing", "by_author", "by_concept"):
        print(f"== {name}")
        for x in report[name][:12]:
            print(f"{x['spend']:9.2f} разход  {x['purchases']:5.0f} пок.  ROAS {x['roas'] if x['roas'] is not None else '-':>5}  {x['ads']:3} рекл.  {x['key'][:70]}")


if __name__ == "__main__":
    main()
