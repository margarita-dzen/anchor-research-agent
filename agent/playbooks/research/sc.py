#!/usr/bin/env python3
"""Scrape Creators API client (Facebook Ad Library, TikTok, Instagram, YouTube, Google, Reddit).

Usable two ways:
  1. As a module:  from sc import ScrapeCreators; sc = ScrapeCreators(); sc.get(path, params, out=...)
  2. As a CLI:     python3 sc.py balance
                   python3 sc.py get /v1/facebook/adLibrary/search/ads query="back pain" country=DE status=ACTIVE trim=true --out raw/test.json
                   (prints the plan only; add --go to actually spend the credit)

Key: env SCRAPECREATORS_API_KEY, else a SCRAPECREATORS_API_KEY=... line in ~/.env.
Cost: 1 credit per request on every endpoint used so far (the free one is /v1/credit-balance).
Standard library only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.scrapecreators.com"
KEY_NAME = "SCRAPECREATORS_API_KEY"
FREE_PATHS = {"/v1/credit-balance"}


def load_key(name=KEY_NAME):
    """Env var first, then ~/.env (simple KEY=VALUE lines, optional 'export ' and quotes)."""
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


class ScrapeCreators:
    def __init__(self, key=None, log_path="run.log", timeout=150, retries=3):
        self.key = key or load_key()
        if not self.key:
            sys.exit(f"No {KEY_NAME} found. Set it in your shell or add {KEY_NAME}=... to ~/.env")
        self.log_path = log_path
        self.timeout = timeout
        self.retries = retries

    def url(self, path, params=None):
        params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        q = urllib.parse.urlencode(params)
        return BASE + path + ("?" + q if q else "")

    def get(self, path, params=None, out=None):
        """GET one endpoint. If `out` exists already it is read from disk (no credit spent).
        Returns parsed JSON or None on failure. Logs credits to run.log."""
        if out and os.path.exists(out):
            with open(out, encoding="utf-8") as fh:
                return json.load(fh)
        req = urllib.request.Request(self.url(path, params), headers={"x-api-key": self.key})
        data = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = r.read()
                break
            except urllib.error.HTTPError as e:
                body = e.read()[:300].decode("utf8", "replace")
                if e.code == 429:
                    wait = int(e.headers.get("retry-after") or 10)
                    print(f"429 rate limited, waiting {wait}s", file=sys.stderr)
                    time.sleep(wait)
                    continue
                if e.code == 404:
                    # Most common cause: using POST, or a wrong path. All endpoints here are GET.
                    self._log(f"ERR 404 {path} {params} (all Scrape Creators endpoints are GET; check the path)")
                    return None
                self._log(f"ERR {e.code} {path} {params} {body}")
                if e.code in (401, 402, 403):
                    return None
                time.sleep(3)
            except Exception as e:  # network hiccup
                print(f"retry {attempt + 1}: {e}", file=sys.stderr)
                time.sleep(4)
        if data is None:
            return None
        try:
            j = json.loads(data)
        except ValueError:
            self._log(f"ERR non-JSON response for {path} {params}")
            return None
        if out:
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(j, fh, ensure_ascii=False)
        self._log(f"{out or path} charged={j.get('credits_charged')} left={j.get('credits_remaining')}")
        return j

    def balance(self):
        """Free. Note: this endpoint can lag behind top-ups; the credits_remaining field
        on any real call is the reliable number."""
        req = urllib.request.Request(BASE + "/v1/credit-balance", headers={"x-api-key": self.key})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def _log(self, msg):
        print(msg)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M ") + "SC " + msg + "\n")

    # ---- Facebook Ad Library helpers (paged with cursor, capped by the API at ~40 ads per query)

    def fb_search_ads(self, query, country="ALL", pages=2, out_prefix=None, sort_by=None):
        """Keyword search in Meta Ad Library. Page 1 = up to 30 ads, page 2 = up to ~10 more.
        Returns a list of page JSONs. 1 credit per page fetched."""
        res, cur = [], None
        for p in range(1, pages + 1):
            prm = {"query": query, "status": "ACTIVE", "trim": "true"}
            if country and country.upper() != "ALL":
                prm["country"] = country.upper()
            if sort_by:
                prm["sort_by"] = sort_by
            if cur:
                prm["cursor"] = cur
            out = f"{out_prefix}_p{p}.json" if out_prefix else None
            j = self.get("/v1/facebook/adLibrary/search/ads", prm, out)
            if not j:
                break
            res.append(j)
            n = len(j.get("searchResults") or [])
            cur = j.get("cursor")
            if not cur or n < 30 or (j.get("searchResultsCount") or 0) <= 30 * p:
                break
        return res

    def fb_company_ads(self, page_id, pages=2, out_prefix=None):
        """All active ads of one Facebook page. Capped at ~40 ads, so '40' means 'at least 40'."""
        res, cur = [], None
        for p in range(1, pages + 1):
            prm = {"pageId": page_id, "status": "ACTIVE", "trim": "true"}
            if cur:
                prm["cursor"] = cur
            out = f"{out_prefix}_p{p}.json" if out_prefix else None
            j = self.get("/v1/facebook/adLibrary/company/ads", prm, out)
            if not j:
                break
            res.append(j)
            n = len(j.get("results") or [])
            cur = j.get("cursor")
            if not cur or n < 25:
                break
        return res


def main():
    ap = argparse.ArgumentParser(
        description="Scrape Creators CLI. 'balance' is free. 'get' costs 1 credit and only runs with --go.",
        epilog="Examples:\n"
        "  python3 sc.py balance\n"
        "  python3 sc.py get /v1/facebook/adLibrary/search/companies query=BrandName --out raw/comp_brand.json\n"
        "  python3 sc.py get /v1/tiktok/video/comments url=https://www.tiktok.com/@user/video/123 --out raw/ttc_x.json --go\n"
        "See references/api-notes.md for the endpoint list.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("balance", help="free credit balance (can lag after a top-up)")
    g = sub.add_parser("get", help="GET one endpoint (1 credit). Dry run unless --go.")
    g.add_argument("path", help="endpoint path, e.g. /v1/facebook/adLibrary/search/ads")
    g.add_argument("params", nargs="*", help="key=value query params")
    g.add_argument("--out", help="save JSON here; if the file exists, nothing is fetched")
    g.add_argument("--go", action="store_true", help="actually call the API and spend the credit")
    g.add_argument("--log", default="run.log", help="credit log file (default run.log)")
    a = ap.parse_args()

    if a.cmd == "balance":
        print(json.dumps(ScrapeCreators(log_path=None).balance(), indent=1))
        return
    params = dict(p.split("=", 1) for p in a.params)
    if a.out and os.path.exists(a.out):
        print(f"cached: {a.out} (no credit spent)")
        return
    if not a.go:
        print("DRY RUN. Would call:")
        print("  GET " + BASE + a.path + "?" + urllib.parse.urlencode(params))
        print("  cost: 1 credit" + ("" if a.path not in FREE_PATHS else " (free endpoint)"))
        print("Add --go after the owner approved the cost.")
        return
    j = ScrapeCreators(log_path=a.log).get(a.path, params, a.out)
    if j is None:
        sys.exit(1)
    if not a.out:
        print(json.dumps(j, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
