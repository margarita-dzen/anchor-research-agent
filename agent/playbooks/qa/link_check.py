#!/usr/bin/env python3
"""Check that links return HTTP 200. Read-only, standard library only.

Sources (combine as needed):
  --urls FILE_OR_URLS   a text file with one URL per line, or URLs given directly
  --ads-json FILE       any JSON (ads.json, live-ads.json, a launch plan): every "link" value found anywhere is checked
  --crawl URL [URL...]  fetch the page(s), collect same-origin <a href>, <img src>, <script src>, <link href> and check them
  --base URL            prefix for links that start with "/"

Reports every URL that is not a direct 200. Redirects are reported too (an ad link should land without a
redirect). Exit code 1 if anything is not 200.
Examples:
  python3 link_check.py --ads-json ads/ads.json --base https://example.com
  python3 link_check.py --crawl https://example.com/xx/article/a1 https://example.com/xx/checkout
"""
import argparse
import concurrent.futures as cf
import html.parser
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def status(url):
    for method in ('HEAD', 'GET'):
        req = urllib.request.Request(url, method=method, headers={'User-Agent': UA})
        try:
            r = OPENER.open(req, timeout=30)
            return r.status, ''
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                return e.code, e.headers.get('Location', '')
            if method == 'HEAD' and e.code in (403, 405, 501):
                continue
            return e.code, ''
        except Exception as e:
            if method == 'HEAD':
                continue
            return 0, str(e)[:120]
    return 0, 'no response'


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        for k in ('href', 'src'):
            v = d.get(k)
            if v and tag in ('a', 'img', 'script', 'link', 'source') and not v.startswith(('mailto:', 'tel:', 'javascript:', '#', 'data:')):
                self.found.append(v)


def find_links(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'link' and isinstance(v, str):
                out.append(v)
            else:
                find_links(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_links(v, out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--urls', nargs='*', default=[], help='URLs, or a text file with one URL per line')
    ap.add_argument('--ads-json', nargs='*', default=[], help='JSON file(s); every "link" field is checked')
    ap.add_argument('--crawl', nargs='*', default=[], help='page URL(s) whose same-origin links are checked')
    ap.add_argument('--base', default='', help='prefix for links starting with /')
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()

    urls = []
    for u in a.urls:
        if os.path.exists(u):
            urls += [l.strip() for l in open(u, encoding='utf8') if l.strip() and not l.startswith('#')]
        else:
            urls.append(u)
    for f in a.ads_json:
        found = []
        find_links(json.load(open(f, encoding='utf8')), found)
        urls += found
    for page in a.crawl:
        req = urllib.request.Request(page, headers={'User-Agent': UA})
        try:
            body = urllib.request.urlopen(req, timeout=30).read().decode('utf8', 'replace')
        except Exception as e:
            print(f'CRAWL FAILED {page}: {e}')
            continue
        p = Links()
        p.feed(body)
        origin = '{0.scheme}://{0.netloc}'.format(urllib.parse.urlparse(page))
        for v in p.found:
            full = urllib.parse.urljoin(page, v).split('#')[0]
            if full.startswith(origin):
                urls.append(full)
        urls.append(page)
    if not urls:
        sys.exit('Nothing to check. Use --urls, --ads-json or --crawl.')
    urls = [(a.base.rstrip('/') + u) if u.startswith('/') else u for u in urls]
    urls = sorted(set(urls))

    bad = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for u, (code, extra) in zip(urls, ex.map(status, urls)):
            if code == 200:
                continue
            bad += 1
            kind = 'REDIRECT' if 300 <= code < 400 else 'FAIL'
            print(f'{kind} {code} {u}' + (f'  -> {extra}' if extra else ''))
    print(f'checked {len(urls)} URLs, not 200: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
