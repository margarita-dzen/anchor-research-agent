#!/usr/bin/env python3
"""Turn raw API JSON into compact text digests that Claude (or a person) can read in one go.

Modes:
  ads       (default) TrendTrack + Meta Ad Library (Scrape Creators) ad files -> digest.txt
            + landing-targets.json (landing URLs ranked by how long and how hard they are pushed)
            + ads.json (every ad normalized, with media URLs, for later look-ups)
  social    TikTok / Instagram / YouTube search files -> list of videos sorted by views
  comments  comment files (TikTok, YouTube, Facebook posts, Instagram, Reddit) -> comments sorted by likes

Examples:
  python3 digest.py ads --raw raw --out digest.txt
  python3 digest.py ads --raw raw --exclude "dog|cat|puppy" --min-days 30 --out digest-proven.txt
  python3 digest.py ads --raw raw --files "raw/fbco__*" --group advertiser --out competitors-digest.txt
  python3 digest.py social --raw raw --region BG,RO --out social-digest.txt
  python3 digest.py comments --raw raw --files "raw/ttc_*" "raw/ytc_*" --out comments-digest.txt

Raw file names follow run_queries.py: <source>__<problem>__<lang>[__<country>][_pN].json.
Other names still work; problem/lang are then left blank. Free: no API calls. Standard library only.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys

NOW = datetime.datetime.now(datetime.timezone.utc).timestamp()
SOCIAL_HOSTS = re.compile(r"(facebook\.com|fb\.me|instagram\.com|m\.me|wa\.me|whatsapp\.com)", re.I)


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError) as e:
        print(f"skip {path}: {e}", file=sys.stderr)
        return None


def name_parts(path):
    base = re.sub(r"_p\d+$", "", os.path.basename(path)[:-5])
    parts = base.split("__")
    src = parts[0]
    prob = parts[1] if len(parts) > 1 else ""
    lang = parts[2] if len(parts) > 2 else ""
    country = parts[3] if len(parts) > 3 else ""
    return src, prob, lang, country


def one_line(s, n):
    s = re.sub(r"\s*\n\s*", " / ", (s or "").strip())
    return s if len(s) <= n else s[:n] + "..."


def norm_url(u):
    u = re.sub(r"[?#].*", "", u or "").rstrip("/").lower()
    return re.sub(r"^https?://(www\.)?", "", u)


# ---------------------------------------------------------------- ads

def from_trendtrack(a):
    adv = a.get("advertiser") or {}
    c = a.get("content") or {}
    m = a.get("metrics") or {}
    au = a.get("audience") or {}
    md = a.get("media") or {}
    days = a.get("daysRunning")
    if days is None and a.get("firstSeenAt"):
        try:
            first = datetime.datetime.fromisoformat(a["firstSeenAt"].replace("Z", "+00:00")).timestamp()
            days = int((NOW - first) / 86400)
        except ValueError:
            days = None
    return dict(
        id=a.get("id"), api="TT", advertiser=adv.get("name"), advertiser_id=adv.get("id"),
        page_id=adv.get("facebookPageId"), days=days, countries=au.get("targetedCountries") or [],
        fmt=md.get("type"), reach=m.get("reach"), spend=m.get("estimatedSpend"), variants=m.get("duplicates"),
        title=c.get("title") or c.get("ctaDescription") or "", body=c.get("body") or "",
        transcript=c.get("transcript") or "", cta=c.get("callToAction"), link=c.get("landingPageUrl") or "",
        media=md.get("mediaUrl") or md.get("thumbnailUrl"), adv_live_ads=adv.get("liveAdsCount"),
    )


def from_fb(a):
    s = a.get("snapshot") or {}
    cards = s.get("cards") or []
    body = s.get("body")
    body = body.get("text", "") if isinstance(body, dict) else (body or "")
    if (not body or "{{" in body) and cards:  # dynamic product ads keep the real text in the cards
        body = cards[0].get("body") or body
    link = s.get("link_url") or (cards[0].get("link_url") if cards else "") or ""
    title = s.get("title") or (cards[0].get("title") if cards else "") or ""
    start = a.get("start_date")
    media = None
    if s.get("videos"):
        media = s["videos"][0].get("video_sd_url") or s["videos"][0].get("video_preview_image_url")
    elif s.get("images"):
        media = s["images"][0].get("original_image_url")
    elif cards:
        media = cards[0].get("video_sd_url") or cards[0].get("original_image_url")
    return dict(
        id=str(a.get("ad_archive_id")), api="FB", advertiser=a.get("page_name") or s.get("page_name"),
        advertiser_id=a.get("page_id"), page_id=a.get("page_id"),
        days=int((NOW - start) / 86400) if start else None,
        countries=a.get("targeted_or_reached_countries") or [], fmt=s.get("display_format"),
        reach=a.get("reach_estimate"), spend=a.get("spend"), variants=a.get("collation_count"),
        title=title, body=body, transcript="", cta=s.get("cta_text"), link=link, media=media, adv_live_ads=None,
    )


def collect_ads(files):
    ads = {}
    for f in files:
        j = load(f)
        if not isinstance(j, dict):
            continue
        src, prob, lang, country = name_parts(f)
        if isinstance(j.get("data"), list):
            rows = [from_trendtrack(a) for a in j["data"]]
        elif isinstance(j.get("searchResults"), list) and j["searchResults"] and "ad_archive_id" in j["searchResults"][0]:
            rows = [from_fb(a) for a in j["searchResults"]]
        elif isinstance(j.get("results"), list) and j["results"] and "ad_archive_id" in j["results"][0]:
            rows = [from_fb(a) for a in j["results"]]
        else:
            continue
        for r in rows:
            if not r["id"] or r["id"] == "None":
                continue
            ex = ads.get(r["id"])
            if ex is None:
                r.update(problems=set(), langs=set(), searched=set(), files=set())
                ads[r["id"]] = ex = r
            if prob and src not in ("ttadv", "fbco"):
                ex["problems"].add(prob)
            if lang:
                ex["langs"].add(lang)
            if country and country.upper() != "ALL":
                ex["searched"].add(country.upper())
            ex["files"].add(src)
    return ads


def ad_line(a, body_chars, tr_chars):
    ctry = ",".join(sorted(set(a["countries"]) | a["searched"])) or "-"
    bits = [f"id={a['id']}", a["advertiser"] or "?", f"days={a['days'] if a['days'] is not None else '?'}", ctry,
            a["fmt"] or "-"]
    if a["reach"]:
        bits.append(f"reach={a['reach']}")
    if a["spend"]:
        bits.append(f"spend~{a['spend']}")
    if a["variants"] and a["variants"] > 1:
        bits.append(f"variants={a['variants']}")
    line = "- " + " | ".join(str(b) for b in bits)
    if a["title"]:
        line += f"\n    TITLE: {one_line(a['title'], 160)}"
    line += f"\n    COPY: {one_line(a['body'], body_chars) or '(no text)'}"
    if a["transcript"] and tr_chars:
        line += f"\n    VIDEO SAYS: {one_line(a['transcript'], tr_chars)}"
    if a["link"]:
        line += f"\n    LP: {a['link']}" + (f"  [CTA {a['cta']}]" if a["cta"] else "")
    return line


def landing_targets(ads):
    by = collections.defaultdict(list)
    for a in ads:
        if a["link"] and not SOCIAL_HOSTS.search(a["link"]):
            by[norm_url(a["link"])].append(a)
    rows = []
    for u, L in by.items():
        days = [x["days"] for x in L if x["days"] is not None] or [0]
        d7 = sum(d <= 7 for d in days)
        d30 = sum(d <= 30 for d in days)
        oldest = max(days)
        # oldest ad = proof it pays; many new ads = it is being scaled right now
        score = d7 * 3 + d30 + 0.3 * len(L) + (5 if oldest > 60 else 0) + min(oldest, 720) / 60
        top = max(L, key=lambda x: x["days"] or 0)
        rows.append(dict(
            url="https://" + u, domain=u.split("/")[0],
            advertiser=collections.Counter(x["advertiser"] for x in L).most_common(1)[0][0],
            ads=len(L), oldest_days=oldest, new_7d=d7, new_30d=d30,
            countries=sorted(set().union(*[set(x["countries"]) | x["searched"] for x in L])),
            problems=sorted(set().union(*[x["problems"] for x in L])),
            example_ad=top["id"], example_copy=one_line(top["body"], 200), score=round(score, 1),
        ))
    rows.sort(key=lambda r: -r["score"])
    return rows


def cmd_ads(a):
    files = expand(a.files) if a.files else sorted(
        f for f in glob.glob(os.path.join(a.raw, "*.json"))
        if name_parts(f)[0] in ("tt", "fb", "ttadv", "fbco") or a.all_files)
    ads = collect_ads(files)
    inc = re.compile(a.include, re.I) if a.include else None
    exc = re.compile(a.exclude, re.I) if a.exclude else None
    exa = re.compile(a.exclude_advertiser, re.I) if a.exclude_advertiser else None
    kept = []
    for x in ads.values():
        text = " ".join([x["body"], x["title"], x["link"], x["transcript"]])
        if inc and not inc.search(text):
            continue
        if exc and exc.search(text):
            continue
        if exa and exa.search(x["advertiser"] or ""):
            continue
        if a.min_days and (x["days"] or 0) < a.min_days:
            continue
        kept.append(x)

    out = []
    out.append(f"# Ad digest  ({datetime.date.today().isoformat()})")
    out.append(f"files read: {len(files)} | unique ads: {len(ads)} | kept after filters: {len(kept)}")
    out.append("days = days the ad has been running (main proof that it pays). reach/spend are estimates. "
               "variants = copies of the same ad. FB advertiser pulls are capped at ~40 ads, so 40 means 'at least 40'.\n")

    # advertiser overview
    byadv = collections.defaultdict(list)
    for x in kept:
        byadv[x["advertiser"] or "?"].append(x)
    out.append("## Advertisers (most ads first)")
    for name, L in sorted(byadv.items(), key=lambda kv: (-len(kv[1]), -max(x["days"] or 0 for x in kv[1]))):
        days = sorted(x["days"] or 0 for x in L)
        ctry = sorted(set().union(*[set(x["countries"]) | x["searched"] for x in L]))
        links = collections.Counter(norm_url(x["link"]) for x in L if x["link"]).most_common(2)
        live = next((x["adv_live_ads"] for x in L if x["adv_live_ads"]), None)
        out.append(f"- {name} | ads={len(L)}" + (f" (live total {live})" if live else "") +
                   f" | oldest={days[-1]}d median={days[len(days) // 2]}d | {','.join(ctry) or '-'} | "
                   + "; ".join(f"{u} x{c}" for u, c in links))
    out.append("")

    # detail
    if a.group == "advertiser":
        groups = {f"ADVERTISER={k}": v for k, v in byadv.items()}
        order = sorted(groups, key=lambda k: -max(x["days"] or 0 for x in groups[k]))
    else:
        groups = collections.defaultdict(list)
        for x in kept:
            keys = [f"PROBLEM={p} LANG={l}" for p in sorted(x["problems"]) or ["-"] for l in sorted(x["langs"]) or ["-"]]
            for k in keys:
                groups[k].append(x)
        order = sorted(groups)
    for k in order:
        L = sorted(groups[k], key=lambda x: -(x["days"] or 0))
        seen, shown = set(), []
        for x in L:  # collapse identical copy so the digest stays short
            sig = (x["advertiser"], (x["body"] or "")[:80])
            if sig in seen:
                continue
            seen.add(sig)
            shown.append(x)
        out.append(f"##### {k} ({len(L)} ads, {len(shown)} distinct)")
        for x in shown[: a.per_group]:
            out.append(ad_line(x, a.body_chars, a.transcript_chars))
        out.append("")

    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    lt = landing_targets(kept)
    lt_path = os.path.join(os.path.dirname(a.out) or ".", "landing-targets.json")
    with open(lt_path, "w", encoding="utf-8") as fh:
        json.dump(lt[: a.top_urls], fh, ensure_ascii=False, indent=1)
    js_path = os.path.join(os.path.dirname(a.out) or ".", "ads.json")
    with open(js_path, "w", encoding="utf-8") as fh:
        json.dump([dict(x, problems=sorted(x["problems"]), langs=sorted(x["langs"]), searched=sorted(x["searched"]),
                        files=sorted(x["files"])) for x in kept], fh, ensure_ascii=False)
    print(f"{a.out}: {len(kept)} ads, {len(byadv)} advertisers, {os.path.getsize(a.out) // 1024} KB")
    print(f"{lt_path}: top {min(len(lt), a.top_urls)} landing URLs | {js_path}: normalized ads")
    for r in lt[:15]:
        print(f"  {r['score']:6.1f}  {r['oldest_days']:4d}d  new30d={r['new_30d']:2d}  ads={r['ads']:3d}  "
              f"{(r['advertiser'] or '')[:24]:24s} {r['url'][:80]}")


# ---------------------------------------------------------------- social

def cmd_social(a):
    files = expand(a.files) if a.files else sorted(
        f for f in glob.glob(os.path.join(a.raw, "*.json")) if name_parts(f)[0] in ("tiktok", "instagram", "youtube"))
    regions = {r.strip().upper() for r in a.region.split(",")} if a.region else None
    vids = {}
    for f in files:
        j = load(f)
        if not isinstance(j, dict):
            continue
        src, prob, lang, _ = name_parts(f)
        for it in j.get("search_item_list") or []:  # TikTok
            v = it.get("aweme_info") or {}
            st = v.get("statistics") or {}
            au = v.get("author") or {}
            vid = v.get("aweme_id")
            vids.setdefault(vid, dict(
                plat="tiktok", id=vid, author=au.get("unique_id"), region=v.get("region") or "",
                views=st.get("play_count") or 0, likes=st.get("digg_count") or 0, comments=st.get("comment_count") or 0,
                date=datetime.date.fromtimestamp(v["create_time"]).isoformat() if v.get("create_time") else "",
                text=v.get("desc") or "", url=f"https://www.tiktok.com/@{au.get('unique_id')}/video/{vid}", q=set()))["q"].add(f"{prob}/{lang}")
        for r in j.get("reels") or []:  # Instagram
            ow = r.get("owner") or {}
            vids.setdefault(r.get("id"), dict(
                plat="instagram", id=r.get("id"), author=ow.get("username"), region="",
                views=r.get("video_view_count") or 0, likes=r.get("like_count") or 0, comments=r.get("comment_count") or 0,
                date=(r.get("taken_at") or "")[:10], text=r.get("caption") or "", url=r.get("url"), q=set()))["q"].add(f"{prob}/{lang}")
        for key in ("videos", "shorts"):  # YouTube
            for v in j.get(key) or []:
                ch = v.get("channel") or {}
                vids.setdefault(v.get("id"), dict(
                    plat="youtube" + ("-short" if key == "shorts" else ""), id=v.get("id"),
                    author=ch.get("handle") or ch.get("title"), region="", views=v.get("viewCountInt") or 0, likes=0,
                    comments=0, date=v.get("publishedTimeText") or "", text=v.get("title") or "", url=v.get("url"),
                    q=set()))["q"].add(f"{prob}/{lang}")
    rows = [v for v in vids.values() if v["id"]]
    if regions:  # only TikTok carries a region; others stay in so you can judge by language
        rows = [v for v in rows if v["plat"] != "tiktok" or v["region"].upper() in regions]
    rows.sort(key=lambda v: -(v["views"] or 0))
    out = [f"# Social digest ({datetime.date.today().isoformat()}): {len(rows)} videos"
           + (f", TikTok filtered to {sorted(regions)}" if regions else ""),
           "Search on these platforms is NOT country-filtered. Judge locality by region (TikTok), language and author.\n"]
    for v in rows[: a.limit]:
        out.append(f"- {v['plat']} | @{v['author'] or '-'} | {v['region'] or '-'} | views={v['views']} likes={v['likes']} "
                   f"comments={v['comments']} | {v['date']} | q={','.join(sorted(v['q']))}\n    {one_line(v['text'], 300)}\n    {v['url']}")
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print(f"{a.out}: {len(rows)} videos")


# ---------------------------------------------------------------- comments

def cmd_comments(a):
    files = expand(a.files) if a.files else sorted(glob.glob(os.path.join(a.raw, "*.json")))
    out, total = [f"# Comments digest ({datetime.date.today().isoformat()})",
                  "likes | text. Read for objections, questions, words customers use, and proof requests.\n"], 0
    for f in files:
        j = load(f)
        if not isinstance(j, dict):
            continue
        rows = []
        for c in j.get("comments") or []:
            text = c.get("text") or c.get("content") or c.get("body") or ""
            likes = c.get("digg_count") or c.get("reaction_count") or c.get("like_count") or \
                (c.get("engagement") or {}).get("likes") or c.get("score") or 0
            if isinstance(text, str) and len(text.strip()) >= a.min_len:
                rows.append((likes if isinstance(likes, int) else 0, text))
        for p in j.get("posts") or []:  # Facebook page posts carry topComments
            for c in p.get("topComments") or []:
                text = c.get("text") or ""
                if len(text.strip()) >= a.min_len:
                    rows.append((c.get("reaction_count") or 0, text))
        if not rows:
            continue
        total += len(rows)
        rows.sort(key=lambda r: -r[0])
        out.append(f"##### {os.path.basename(f)} ({len(rows)} comments)")
        for likes, text in rows[: a.per_file]:
            out.append(f"  {likes:>5} | {one_line(text, 400)}")
        out.append("")
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print(f"{a.out}: {total} comments")


def expand(patterns):
    files = []
    for p in patterns:
        files += glob.glob(p) if any(ch in p for ch in "*?[") else [p]
    return sorted(set(f for f in files if f.endswith(".json")))


def main():
    ap = argparse.ArgumentParser(description="Raw research JSON -> compact text digests (free, offline).",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode")
    for m in ("ads", "social", "comments"):
        p = sub.add_parser(m)
        p.add_argument("--raw", default="raw", help="folder with raw JSON (default ./raw)")
        p.add_argument("--files", nargs="*", help="explicit files or globs instead of the whole raw folder")
        p.add_argument("--out", default={"ads": "digest.txt", "social": "social-digest.txt",
                                         "comments": "comments-digest.txt"}[m])
        if m == "ads":
            p.add_argument("--group", choices=["problem", "advertiser"], default="problem")
            p.add_argument("--include", help="regex: keep only ads whose copy/title/link matches (relevance filter)")
            p.add_argument("--exclude", help="regex: drop ads whose copy/title/link matches (keyword noise)")
            p.add_argument("--exclude-advertiser", help="regex on advertiser name to drop")
            p.add_argument("--min-days", type=int, default=0)
            p.add_argument("--per-group", type=int, default=40, help="max distinct ads per group (default 40)")
            p.add_argument("--body-chars", type=int, default=500)
            p.add_argument("--transcript-chars", type=int, default=250)
            p.add_argument("--top-urls", type=int, default=60, help="landing URLs kept in landing-targets.json")
            p.add_argument("--all-files", action="store_true", help="read every JSON in --raw, not just tt/fb/ttadv/fbco")
        if m == "social":
            p.add_argument("--region", help="comma list of TikTok regions to keep, e.g. BG,RO")
            p.add_argument("--limit", type=int, default=150)
        if m == "comments":
            p.add_argument("--min-len", type=int, default=8, help="skip comments shorter than this (emoji-only etc.)")
            p.add_argument("--per-file", type=int, default=80)
    a = ap.parse_args()
    if not a.mode:
        ap.print_help()
        return
    {"ads": cmd_ads, "social": cmd_social, "comments": cmd_comments}[a.mode](a)


if __name__ == "__main__":
    main()
