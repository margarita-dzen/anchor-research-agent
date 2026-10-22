"""Сваля визиите на най-силните реклами веднага след свалянето: fbcdn линковете изтичат след дни.

    python3 agent/adlib/thumbs.py runs/example/run.json [--limit 50]

Брой по продукт: thumbs.per_product (иначе thumbs.default), подредени по дни + 15 × дубликати.
Файлове: <output_dir>/thumbs/<meta_ad_id>.jpg; в ads_all.json се записва thumb_file.
"""
import argparse, io, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runconfig  # noqa: E402


def score(a):
    return (a.get("days_running") or 0) + 15 * (a.get("duplicates") or 1)


def pick(ads, per_product, default, limit=None):
    out = []
    for p in sorted({a.get("product") for a in ads}, key=str):
        n = per_product.get(p, default)
        out += sorted([a for a in ads if a.get("product") == p and a.get("thumb")], key=lambda a: -score(a))[:n]
    return out[:limit] if limit else out


def download(a, tdir, size):
    from PIL import Image
    f = os.path.join(tdir, f"{a['meta_ad_id']}.jpg")
    if os.path.exists(f):
        return True
    try:
        req = urllib.request.Request(a["thumb"], headers={"User-Agent": "Mozilla/5.0"})
        im = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")
        im.thumbnail(tuple(size))
        im.save(f, "JPEG", quality=58, optimize=True)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    cfg = runconfig.load(a.run)
    tc = cfg["thumbs"]
    src = runconfig.path(cfg, "ads_all.json")
    ads = json.load(open(src))
    tdir = runconfig.path(cfg, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    todo = pick(ads, tc["per_product"], tc["default"], a.limit)
    with ThreadPoolExecutor(12) as ex:
        ok = list(ex.map(lambda x: download(x, tdir, tc["max_size"]), todo))
    for x in ads:
        f = os.path.join(tdir, f"{x['meta_ad_id']}.jpg")
        if os.path.exists(f):
            x["thumb_file"] = os.path.relpath(f, cfg["_dir"])
    json.dump(ads, open(src, "w"), ensure_ascii=False, indent=1)
    print(f"{sum(ok)}/{len(todo)} визии -> {tdir}")


if __name__ == "__main__":
    main()
