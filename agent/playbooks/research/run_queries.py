#!/usr/bin/env python3
"""Run a competitor ad research sweep from queries.json, with caching and a credit log.

Default is a DRY RUN: it lists every request that is not cached yet and prints the credit
estimate per API, then stops. Nothing is spent until you add --go (after the owner approved
the estimate).

  python3 run_queries.py queries.json                 # plan + estimate only
  python3 run_queries.py queries.json --only tt       # plan for TrendTrack only
  python3 run_queries.py queries.json --go            # run everything in the plan
  python3 run_queries.py queries.json --go --only fb,adv

Sources (--only): tt = TrendTrack ad copy search, fb = Meta Ad Library keyword search (Scrape Creators),
social = TikTok / Instagram / YouTube search (Scrape Creators), adv = full pulls of named advertisers.

Files land in <raw>/ (default ./raw). A file that exists is never fetched again, so a run that
stops halfway can simply be started again. Every paid call is appended to run.log with its cost.
Standard library only; needs sc.py and trendtrack.py next to it.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TT_PER_AD = 1.5
TT_PER_AD_ADV = 3.0
SOCIAL_PATHS = {
    "tiktok": ("/v1/tiktok/search/keyword", "query"),
    "instagram": ("/v2/instagram/reels/search", "query"),
    "youtube": ("/v1/youtube/search", "query"),
}


def slug(s):
    s = re.sub(r"\s+", "-", str(s).strip())
    return re.sub(r"[^\w\-.]", "", s, flags=re.UNICODE)[:60]


def strip_private(d):
    return {k: v for k, v in d.items() if not str(k).startswith("_")}


def build_jobs(cfg, raw, only):
    langs = cfg.get("languages") or []
    probs = strip_private(cfg.get("problems") or {})
    fbc = cfg.get("fb_country") or {}
    jobs, warnings = [], []

    for prob, terms in probs.items():
        if len(terms) != len(langs):
            warnings.append(f"problem '{prob}' has {len(terms)} terms but {len(langs)} languages; extra/missing ones are skipped")

    def pairs():
        for prob, terms in probs.items():
            for lang, term in zip(langs, terms):
                if term:
                    yield prob, lang, term

    tt = cfg.get("trendtrack") or {}
    if tt.get("on") and "tt" in only:
        limit = int(tt.get("limit", 25))
        by_lang = tt.get("min_days_by_language") or {}
        for prob, lang, term in pairs():
            md = int(by_lang.get(lang, tt.get("min_days_running", 0)) or 0)
            out = os.path.join(raw, f"tt__{prob}__{lang}.json")
            jobs.append(dict(src="tt", api="TrendTrack", out=out, term=term, limit=limit, min_days=md,
                             est=limit * TT_PER_AD, label=f"{prob} [{lang}] '{term}'" + (f" min {md}d" if md else "")))

    fb = cfg.get("fb_adlibrary") or {}
    if fb.get("on") and "fb" in only:
        pages = int(fb.get("pages", 2))
        for prob, lang, term in pairs():
            country = fbc.get(lang, "ALL")
            prefix = os.path.join(raw, f"fb__{prob}__{lang}__{slug(country)}")
            todo = [p for p in range(1, pages + 1) if not os.path.exists(f"{prefix}_p{p}.json")]
            if todo:
                jobs.append(dict(src="fb", api="ScrapeCreators", prefix=prefix, term=term, country=country, pages=pages,
                                 est=len(todo), label=f"{prob} [{lang}/{country}] '{term}' up to {len(todo)} page(s)"))

    so = cfg.get("social") or {}
    if so.get("on") and "social" in only:
        slangs = set(so.get("languages") or langs)
        for prob, lang, term in pairs():
            if lang not in slangs:
                continue
            for plat in so.get("platforms") or []:
                if plat not in SOCIAL_PATHS:
                    warnings.append(f"unknown social platform '{plat}' (use tiktok, instagram, youtube)")
                    continue
                path, param = SOCIAL_PATHS[plat]
                out = os.path.join(raw, f"{plat}__{prob}__{lang}.json")
                jobs.append(dict(src="social", api="ScrapeCreators", out=out, path=path, params={param: term},
                                 est=1, label=f"{plat} {prob} [{lang}] '{term}'"))

    adv = cfg.get("advertisers") or {}
    if "adv" in only:
        for name, aid in strip_private(adv.get("trendtrack_ids") or {}).items():
            lim = int(adv.get("trendtrack_limit", 25))
            out = os.path.join(raw, f"ttadv__{slug(name)}.json")
            jobs.append(dict(src="adv-tt", api="TrendTrack", out=out, aid=str(aid), limit=lim,
                             est=lim * TT_PER_AD_ADV, label=f"advertiser {name} ({aid}) up to {lim} ads"))
        for name, pid in strip_private(adv.get("facebook_page_ids") or {}).items():
            pages = int(adv.get("fb_pages", 2))
            prefix = os.path.join(raw, f"fbco__{slug(name)}")
            todo = [p for p in range(1, pages + 1) if not os.path.exists(f"{prefix}_p{p}.json")]
            if todo:
                jobs.append(dict(src="adv-fb", api="ScrapeCreators", prefix=prefix, pid=str(pid), pages=pages,
                                 est=len(todo), label=f"fb page {name} ({pid}) up to {len(todo)} page(s)"))

    jobs = [j for j in jobs if not (j.get("out") and os.path.exists(j["out"]))]
    return jobs, warnings


def main():
    ap = argparse.ArgumentParser(description="Plan (default) or run (--go) a research sweep from queries.json.",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", help="path to queries.json (see templates/queries.example.json)")
    ap.add_argument("--raw", default="raw", help="folder for raw JSON (default ./raw)")
    ap.add_argument("--only", default="tt,fb,social,adv", help="comma list of sources: tt,fb,social,adv")
    ap.add_argument("--go", action="store_true", help="spend credits and run the plan")
    ap.add_argument("--log", default="run.log", help="credit log (default ./run.log)")
    a = ap.parse_args()

    with open(a.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    only = {s.strip() for s in a.only.split(",") if s.strip()}
    os.makedirs(a.raw, exist_ok=True)
    jobs, warnings = build_jobs(cfg, a.raw, only)

    for w in warnings:
        print("WARNING:", w)
    if not jobs:
        print("Nothing to fetch: every request in this plan is already cached in", a.raw)
        return

    tt_est = sum(j["est"] for j in jobs if j["api"] == "TrendTrack")
    sc_est = sum(j["est"] for j in jobs if j["api"] == "ScrapeCreators")
    print(f"PLAN for '{cfg.get('name', a.config)}': {len(jobs)} request group(s) not cached yet\n")
    for j in jobs:
        print(f"  [{j['src']:6s}] {j['label']}  ~{j['est']:.0f} cr")
    print("\nESTIMATE (maximum; real cost is lower when fewer ads come back):")
    if tt_est:
        print(f"  TrendTrack:     ~{tt_est:,.0f} credits (~{tt_est / 1000:.2f} USD at 1,000 credits = 1 USD)")
    if sc_est:
        print(f"  Scrape Creators: up to {sc_est:,.0f} credits (1 per request)")
    if not a.go:
        print("\nDRY RUN. Nothing was spent. Show this estimate to the owner; after an explicit OK, rerun with --go.")
        return

    sc = tt = None
    if any(j["api"] == "ScrapeCreators" for j in jobs):
        from sc import ScrapeCreators
        sc = ScrapeCreators(log_path=a.log)
    if any(j["api"] == "TrendTrack" for j in jobs):
        from trendtrack import TrendTrack
        tt = TrendTrack(log_path=a.log)

    with open(a.log, "a", encoding="utf-8") as fh:
        fh.write(f"--- run start: {cfg.get('name', a.config)} ({len(jobs)} groups, est TT {tt_est:.0f} / SC {sc_est:.0f})\n")
    for j in jobs:
        if j["src"] == "tt":
            tt.query_ads(j["term"], out=j["out"], limit=j["limit"], min_days=j["min_days"])
        elif j["src"] == "adv-tt":
            tt.advertiser_ads(j["aid"], out=j["out"], limit=j["limit"])
        elif j["src"] == "fb":
            sc.fb_search_ads(j["term"], country=j["country"], pages=j["pages"], out_prefix=j["prefix"])
        elif j["src"] == "adv-fb":
            sc.fb_company_ads(j["pid"], pages=j["pages"], out_prefix=j["prefix"])
        elif j["src"] == "social":
            sc.get(j["path"], j["params"], j["out"])
    with open(a.log, "a", encoding="utf-8") as fh:
        fh.write("--- run done\n")
    print("done. Credits per call are in", a.log)


if __name__ == "__main__":
    main()
