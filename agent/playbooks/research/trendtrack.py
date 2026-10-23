#!/usr/bin/env python3
"""TrendTrack API client (Facebook ad spy data, effectively EU-only).

Usable two ways:
  1. As a module:  from trendtrack import TrendTrack; tt = TrendTrack(); tt.query_ads("back pain", out="raw/x.json")
  2. As a CLI:
       python3 trendtrack.py me                      (free)
       python3 trendtrack.py usage                   (free)
       python3 trendtrack.py lookup competitor.com   (free: find an advertiser id from a domain)
       python3 trendtrack.py query "Rückenschmerzen" --min-days 60 --out raw/test.json   (dry run, add --go)
       python3 trendtrack.py advertiser-ads 1234567890 --out raw/adv_x.json                (dry run, add --go)

Key: env TRENDTRACK_API_KEY, else a TRENDTRACK_API_KEY=... line in ~/.env.
Cost seen in practice: about 1.5 credits per ad returned by /v1/ads/query (25 ads = 38 credits),
about 3 credits per ad on advertiser ads. 1,000 credits = 1 USD. Standard library only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.trendtrack.io"
KEY_NAME = "TRENDTRACK_API_KEY"
CREDITS_PER_AD_QUERY = 1.5
CREDITS_PER_AD_ADVERTISER = 3.0


def load_key(name=KEY_NAME):
    val = os.environ.get(name)
    if val:
        return val.strip()
    path = os.path.expanduser("~/.env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:].strip()
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def query_body(term, limit=25, min_days=0, status="active", sort_by="longestRunning", search_type="adCopy"):
    body = {
        "search": [term],
        "searchType": search_type,       # adCopy = search the ad text
        "platforms": ["facebook"],       # data is Facebook only
        "status": status,
        "sortBy": sort_by,               # longestRunning puts the proven ads first
        "order": "desc",
        "limit": limit,
    }
    if min_days:
        body["minDaysRunning"] = min_days  # the "proven abroad" filter; works
    return body


class TrendTrack:
    def __init__(self, key=None, log_path="run.log", timeout=60, retries=4):
        self.key = key or load_key()
        if not self.key:
            sys.exit(f"No {KEY_NAME} found. Set it in your shell or add {KEY_NAME}=... to ~/.env")
        self.log_path = log_path
        self.timeout = timeout
        self.retries = retries

    def _request(self, method, path, body=None, params=None):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": "Bearer " + self.key}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read()
                    meta = {"cost": r.headers.get("x-usage-cost"), "left": r.headers.get("x-credits-remaining")}
                return json.loads(raw), meta
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = int(e.headers.get("retry-after") or 10)
                    print(f"429 rate limited, waiting {wait}s", file=sys.stderr)
                    time.sleep(wait)
                    continue
                self._log(f"ERR {e.code} {method} {path} {e.read()[:200].decode('utf8', 'replace')}")
                return None, {}
            except Exception as e:
                print(f"retry {attempt + 1}: {e}", file=sys.stderr)
                time.sleep(4)
        return None, {}

    def _log(self, msg):
        print(msg)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M ") + "TT " + msg + "\n")

    def _save(self, j, out):
        if out:
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(j, fh, ensure_ascii=False)

    # free
    def me(self):
        return self._request("GET", "/v1/me")[0]

    def usage(self):
        return self._request("GET", "/v1/usage")[0]

    def lookup(self, q, kind="auto"):
        return self._request("GET", "/v1/lookup", params={"q": q, "type": kind})[0]

    # paid
    def query_ads(self, term, out=None, **kw):
        if out and os.path.exists(out):
            with open(out, encoding="utf-8") as fh:
                return json.load(fh)
        j, meta = self._request("POST", "/v1/ads/query", body=query_body(term, **kw))
        if j is None:
            return None
        self._save(j, out)
        self._log(f"{out or term} ads={len(j.get('data') or [])} cost={meta.get('cost')} left={meta.get('left')}")
        time.sleep(1.2)  # stay polite; the API rate-limits bursts
        return j

    def advertiser_ads(self, advertiser_id, out=None, limit=25, status="active", sort_by="longestRunning"):
        if out and os.path.exists(out):
            with open(out, encoding="utf-8") as fh:
                return json.load(fh)
        params = {"status": status, "sortBy": sort_by, "limit": limit}
        j, meta = self._request("GET", f"/v1/advertisers/{advertiser_id}/ads", params=params)
        if j is None:
            return None
        self._save(j, out)
        self._log(f"{out or advertiser_id} ads={len(j.get('data') or [])} cost={meta.get('cost')} left={meta.get('left')}")
        time.sleep(1.2)
        return j


def main():
    ap = argparse.ArgumentParser(
        description="TrendTrack CLI. me/usage/lookup are free. query/advertiser-ads spend credits and only run with --go.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Credits: ~1.5 per ad on query (25 ads ~ 38), ~3 per ad on advertiser-ads.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("me", help="free: account and plan")
    sub.add_parser("usage", help="free: credits used / left")
    lk = sub.add_parser("lookup", help="free: find advertiser by domain or name")
    lk.add_argument("q")
    lk.add_argument("--type", default="auto")
    q = sub.add_parser("query", help="search active Facebook ads by ad copy (paid)")
    q.add_argument("term")
    q.add_argument("--limit", type=int, default=25)
    q.add_argument("--min-days", type=int, default=0, help="minDaysRunning, e.g. 60 = proven ads only")
    q.add_argument("--out")
    q.add_argument("--go", action="store_true")
    ad = sub.add_parser("advertiser-ads", help="active ads of one advertiser id (paid)")
    ad.add_argument("advertiser_id")
    ad.add_argument("--limit", type=int, default=25)
    ad.add_argument("--out")
    ad.add_argument("--go", action="store_true")
    a = ap.parse_args()

    if a.cmd in ("me", "usage", "lookup"):
        tt = TrendTrack(log_path=None)
        res = tt.me() if a.cmd == "me" else tt.usage() if a.cmd == "usage" else tt.lookup(a.q, a.type)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    if a.out and os.path.exists(a.out):
        print(f"cached: {a.out} (no credit spent)")
        return
    if a.cmd == "query":
        est = a.limit * CREDITS_PER_AD_QUERY
        plan = f"POST {BASE}/v1/ads/query {json.dumps(query_body(a.term, a.limit, a.min_days), ensure_ascii=False)}"
    else:
        est = a.limit * CREDITS_PER_AD_ADVERTISER
        plan = f"GET {BASE}/v1/advertisers/{a.advertiser_id}/ads?status=active&sortBy=longestRunning&limit={a.limit}"
    if not a.go:
        print("DRY RUN. Would call:\n  " + plan)
        print(f"  max cost: ~{est:.0f} credits (fewer if fewer ads come back)")
        print("Add --go after the owner approved the cost.")
        return
    tt = TrendTrack()
    j = tt.query_ads(a.term, out=a.out, limit=a.limit, min_days=a.min_days) if a.cmd == "query" \
        else tt.advertiser_ads(a.advertiser_id, out=a.out, limit=a.limit)
    if j is None:
        sys.exit(1)
    if not a.out:
        print(json.dumps(j, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
