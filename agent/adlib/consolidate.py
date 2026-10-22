"""Обединява суровите файлове от raw/ в ads_all.json: по един запис на collation група.

    python3 agent/adlib/consolidate.py runs/example/run.json [--raw-dir ДРУГА/raw] [--out ads_all.json]

Темите (categories), белезите (flags), изключенията и правилата за продукт идват от run.json.
Формат на записа (чете го agent/evidence.py): meta_ad_id, collation_id, brand, page_id, first_seen,
days_running, active, format, headline, primary_text, landing_url, landing_url_clean, domain, duplicates,
thumb, video, cta, countries, queries, cats, rel_<категория>, <белег> + flags, product,
и ако ги има: eu_reach / eu_reach_countries (eu_reach.py), thumb_file (thumbs.py).
"""
import argparse, collections, datetime, glob, json, os, re, sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runconfig  # noqa: E402

BAD_CHARS = "�"  # U+FFFD чупи публикуването на artifact


def clean_text(s):
    return (s or "").replace(BAD_CHARS, "").strip()


def read_raw(path):
    """(meta, ads) от нов файл {meta, ads} или стар списък с име <cat>__<CC>__<заявка>.json."""
    d = runconfig.read_json(path)
    if isinstance(d, dict):
        return d.get("meta") or {}, d.get("ads") or []
    cat, cc, q = os.path.basename(path)[:-5].split("__", 2)
    meta = dict(cat=cat, country=cc, q=q, mode="keyword")
    if cat == "page":
        meta.update(mode="page", page_id=q, q=None)
    return meta, d


def raw_files(raw_dir):
    return sorted(f for f in glob.glob(os.path.join(raw_dir, "*.json")) if not os.path.basename(f).startswith("_"))


def _ts(x):
    return datetime.datetime.utcfromtimestamp(x).date() if x else None


def ad_record(o, meta, cfg, today):
    """Един суров обект от Ad Library → запис. None, ако попада в exclude."""
    s = o.get("snapshot") or {}
    cards = s.get("cards") or []
    c0 = cards[0] if cards else {}
    body = ((s.get("body") or {}).get("text") or "") or c0.get("body") or ""
    if "{{product" in body:  # каталожна (DPA) реклама: текстът е в картата
        body = c0.get("body") or body
    title = s.get("title") or c0.get("title") or ""
    link = s.get("link_url") or c0.get("link_url") or ""
    brand = s.get("page_name") or o.get("page_name") or ""
    if cfg.get("exclude") and re.search(cfg["exclude"], link + " " + brand, re.I):
        return None
    txt = f"{title}\n{body}\n{link}"
    start, end = _ts(o.get("start_date")), _ts(o.get("end_date")) or today
    if o.get("is_active"):
        end = today
    imgs = [i.get("resized_image_url") or i.get("original_image_url") for i in (s.get("images") or [])]
    imgs += [c.get("resized_image_url") or c.get("original_image_url") for c in cards
             if c.get("resized_image_url") or c.get("original_image_url")]
    vids = s.get("videos") or []
    thumb = imgs[0] if imgs else (vids[0].get("video_preview_image_url") if vids else None) or c0.get("video_preview_image_url")
    fmt = (s.get("display_format") or "").lower()
    fmt = "video" if "video" in fmt or vids else "carousel" if fmt in ("carousel", "dco") and len(cards) > 1 else "image"
    u = urlparse(link)
    q = meta.get("q") or (f"page:{meta.get('page_id')}" if meta.get("page_id") else "")
    r = dict(meta_ad_id=o["ad_archive_id"], collation_id=o.get("collation_id"), brand=clean_text(brand),
             page_id=o.get("page_id"), first_seen=str(start) if start else None,
             days_running=(end - start).days if start else None, active=bool(o.get("is_active")),
             format=fmt, headline=clean_text(title), primary_text=clean_text(body), landing_url=link,
             landing_url_clean=f"{u.scheme}://{u.netloc}{u.path}" if u.netloc else "",
             domain=u.netloc.lower().replace("www.", ""), duplicates=o.get("collation_count") or 1, thumb=thumb,
             video=(vids[0].get("video_hd_url") or vids[0].get("video_sd_url")) if vids else None,
             cta=s.get("cta_text"), countries={meta.get("country") or ""} - {""}, queries={q} - {""},
             cats={meta.get("cat") or ""} - {""})
    for name, rx in cfg["flags"].items():
        r[name] = bool(re.search(rx, txt, re.I))
    r["flags"] = [n for n in cfg["flags"] if r[n]]
    for name, rx in cfg["categories"].items():
        r[f"rel_{name}"] = bool(re.search(rx, txt, re.I))
    return r


def merge(rec, r, flag_names=()):
    rec["countries"] |= r["countries"]
    rec["queries"] |= r["queries"]
    rec["cats"] |= r["cats"]
    rec["duplicates"] = max(rec["duplicates"], r["duplicates"])
    rec["active"] = rec["active"] or r["active"]
    if (r["days_running"] or 0) > (rec["days_running"] or 0):
        rec.update(days_running=r["days_running"], first_seen=r["first_seen"])
    for k, v in r.items():  # белезите и темите: вярно, ако е вярно в някой от вариантите
        if (k.startswith("rel_") or k in flag_names) and v:
            rec[k] = True


def classify(r, rules, unmatched="drop"):
    """Първото правило, което пасва: cats (поне една от категориите на заявката), require (всички теми),
    exclude (нито една тема). Без съвпадение: unmatched ("drop" = None)."""
    for rule in rules:
        if rule.get("cats") and not set(rule["cats"]) & set(r["cats"]):
            continue
        if not all(r.get(f"rel_{c}") for c in rule.get("require", [])):
            continue
        if any(r.get(f"rel_{c}") for c in rule.get("exclude", [])):
            continue
        return rule["product"]
    return None if unmatched == "drop" else unmatched


def consolidate(sources, cfg, today):
    """sources: [(meta, ads)]. Връща списъка записи, подреден по дни на въртене."""
    groups = {}
    for meta, raw in sources:
        for o in raw:
            if not o.get("ad_archive_id"):
                continue
            r = ad_record(o, meta, cfg, today)
            if r is None:
                continue
            key = o.get("collation_id") or o["ad_archive_id"]
            if key in groups:
                merge(groups[key], r, cfg["flags"])
            else:
                groups[key] = r
    out = []
    for r in groups.values():
        r["product"] = classify(r, cfg["products"], cfg.get("unmatched", "drop"))
        if r["product"] is None:
            continue
        r["flags"] = [n for n in cfg["flags"] if r[n]]
        for k in ("countries", "queries", "cats"):
            r[k] = sorted(r[k])
        out.append(r)
    out.sort(key=lambda r: -(r["days_running"] or 0))
    return out


def attach_extras(ads, cfg):
    """Връща в записите вече събраното: EU обхват от кеша и локалните визии."""
    cache_f = runconfig.path(cfg, "eu_reach_cache.json")
    cache = runconfig.read_json(cache_f) if os.path.exists(cache_f) else {}
    tdir = runconfig.path(cfg, "thumbs")
    for a in ads:
        c = cache.get(a["meta_ad_id"])
        if c:
            a["eu_reach"] = c.get("eu_reach")
            a["eu_reach_countries"] = c.get("countries") or []
        f = os.path.join(tdir, f"{a['meta_ad_id']}.jpg")
        if os.path.exists(f):
            a["thumb_file"] = os.path.relpath(f, cfg["_dir"])
    return ads


def summary(ads):
    lines = [f"{len(ads)} записа · " + ", ".join(f"{k} {v}" for k, v in collections.Counter(a['product'] for a in ads).most_common())]
    for p in sorted({a["product"] for a in ads}):
        c, d = collections.Counter(), {}
        for a in ads:
            if a["product"] == p:
                c[a["brand"]] += 1
                d[a["brand"]] = max(d.get(a["brand"], 0), a["days_running"] or 0)
        lines.append(f"== {p}: " + ", ".join(f"{b} ({n}, {d[b]} дни)" for b, n in c.most_common(15)))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--raw-dir", help="по подразбиране <output_dir>/raw")
    ap.add_argument("--out", help="по подразбиране <output_dir>/ads_all.json")
    a = ap.parse_args()
    cfg = runconfig.load(a.run)
    today = runconfig.scrape_date(cfg)
    files = raw_files(a.raw_dir or runconfig.path(cfg, "raw"))
    ads = attach_extras(consolidate([read_raw(f) for f in files], cfg, today), cfg)
    out = a.out or runconfig.path(cfg, "ads_all.json")
    json.dump(ads, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"дата {today} · {len(files)} файла -> {out}")
    print(summary(ads))


if __name__ == "__main__":
    main()
