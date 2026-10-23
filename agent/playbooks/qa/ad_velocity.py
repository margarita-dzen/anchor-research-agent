#!/usr/bin/env python3
"""Rank landing URLs by ad launch velocity from cached Ad Library pulls (adlib_sweep.py output).

Reads every fb_*.json (keyword search) and co_*.json (page pull) in the input folder(s), deduplicates ads,
groups them by normalised landing URL and scores each URL:
  score = 3 * ads started in the last 7 days + ads started in the last 30 days
          + 0.3 * all ads + 5 if the oldest ad is over 60 days old
Many fresh variants = being scaled now. 60+ days running = profitable. Counts are relative signals only
(the Ad Library caps each pull at about 30-40 ads).

Writes <out>/velocity.json (ranked URLs with markets, pages, sample text, ad ids) and <out>/all_ads.json,
and prints the top rows. Local files only, no API calls, standard library only.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re


def norm(u):
    u = re.sub(r'[?#].*', '', u or '').rstrip('/').lower()
    return re.sub(r'^https?://(www\.)?', '', u)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('raw', nargs='+', help='folder(s) with fb_*.json / co_*.json')
    ap.add_argument('--out', default='research', help='output folder (default research)')
    ap.add_argument('--today', help='reference date YYYY-MM-DD (default: today)')
    ap.add_argument('--top', type=int, default=50, help='rows to print')
    a = ap.parse_args()

    now = (datetime.datetime.strptime(a.today, '%Y-%m-%d') if a.today else datetime.datetime.now()).timestamp()
    ads = {}

    def add(ad, src, cc=None):
        s = ad.get('snapshot') or {}
        cards = s.get('cards') or []
        body = s.get('body')
        body = body.get('text', '') if isinstance(body, dict) else (body or '')
        if (not body or '{{' in body) and cards:
            body = cards[0].get('body') or body
        link = s.get('link_url') or (cards[0].get('link_url') if cards else '') or ''
        k = ad.get('ad_archive_id') or ad.get('adArchiveID') or ad.get('id')
        if not k:
            return
        imgs = s.get('images') or []
        r = ads.setdefault(k, dict(
            id=k, page=ad.get('page_name'), page_id=ad.get('page_id'), start=ad.get('start_date') or now,
            link=link, body=body, title=s.get('title') or (cards[0].get('title') if cards else '') or '',
            fmt=s.get('display_format'), c=set(), src=set(),
            img=(imgs[0].get('original_image_url') if imgs else (cards[0].get('original_image_url') if cards else None))))
        if cc:
            r['c'].add(cc)
        for x in (ad.get('targeted_or_reached_countries') or []):
            r['c'].add(x)
        r['src'].add(src)

    files = 0
    for d in a.raw:
        for f in glob.glob(os.path.join(d, 'fb_*.json')):
            cc = os.path.basename(f).split('_')[1]
            for ad in (json.load(open(f, encoding='utf8')).get('searchResults') or []):
                add(ad, 'kw', cc)
            files += 1
        for f in glob.glob(os.path.join(d, 'co_*.json')):
            for ad in (json.load(open(f, encoding='utf8')).get('results') or []):
                add(ad, 'co')
            files += 1

    by_url = collections.defaultdict(list)
    for v in ads.values():
        L = v['link']
        if L and not any(x in L for x in ('instagram.com', 'fb.me', 'facebook.com')):
            by_url[norm(L)].append(v)

    rows = []
    for u, vs in by_url.items():
        ages = [(now - float(v['start'])) / 86400 for v in vs]
        d7 = sum(x <= 7 for x in ages)
        d30 = sum(x <= 30 for x in ages)
        d90 = sum(x <= 90 for x in ages)
        oldest = int(max(ages))
        rows.append(dict(
            url=u, page=collections.Counter(v['page'] for v in vs).most_common(1)[0][0], n=len(vs),
            d7=d7, d30=d30, d90=d90, oldest=oldest,
            markets=sorted(set().union(*[v['c'] for v in vs])),
            score=round(d7 * 3 + d30 + 0.3 * len(vs) + (5 if oldest > 60 else 0), 1),
            sample=max(vs, key=lambda v: len(v['body'] or ''))['body'][:400],
            ids=[v['id'] for v in vs][:5]))
    rows.sort(key=lambda r: -r['score'])

    os.makedirs(a.out, exist_ok=True)
    json.dump(rows, open(os.path.join(a.out, 'velocity.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    json.dump([dict(v, c=sorted(v['c']), src=sorted(v['src'])) for v in ads.values()],
              open(os.path.join(a.out, 'all_ads.json'), 'w', encoding='utf8'), ensure_ascii=False)
    print(f'files {files}, ads {len(ads)}, landing URLs {len(rows)} -> {a.out}/velocity.json, all_ads.json')
    print(' score    n  7d 30d 90d oldest markets              page                     url')
    for r in rows[:a.top]:
        print(f"{r['score']:6.1f} {r['n']:4d} {r['d7']:3d} {r['d30']:3d} {r['d90']:3d} {r['oldest']:6d} "
              f"{','.join(r['markets'])[:20]:20s} {str(r['page'])[:24]:24s} {r['url'][:80]}")


if __name__ == '__main__':
    main()
