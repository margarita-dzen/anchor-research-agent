"""Конфигурация на едно пускане (runs/<име>/run.json). Нищо клиентско не стои в кода.

Ключове (пример: runs/example/run.json):
  queries     [{cat, country, q}]       ключови думи по категория × пазар
  categories  {име: regex}              тема на рекламата (rel_<име>); категорията на заявката е в cats
  flags       {име: regex}              допълнителни белези (напр. mom, herbal), полета <име> + списък flags
  exclude     regex                     линк/страница за изхвърляне (temu, amazon...)
  products    [{product, cats, require, exclude}]  първото съвпадение определя product
  unmatched   "drop" или име на продукт за всичко без съвпадение
  output_dir  папка за raw/, ads_all.json, thumbs/ (спрямо run.json)
  scrape_date YYYY-MM-DD или null (тогава датата от raw/_meta.json, после днешната)
  scrape      {scrolls, parallel (макс. 2), retries, active}
  pages       {country, scrolls, top, ids, products}  пълно сваляне по страница
  thumbs      {per_product {име: брой}, default, max_size [ш, в]}
  eu_reach    {top, products}
"""
import datetime, json, os, re

MAX_PARALLEL = 2  # над 2 паралелни FB пренасочва и връща 0 реклами

DEFAULTS = {
    "queries": [], "categories": {}, "flags": {}, "exclude": "", "products": [], "unmatched": "drop",
    "output_dir": ".", "scrape_date": None,
    "scrape": {"scrolls": 7, "parallel": 2, "retries": 2, "active": "active"},
    "pages": {"country": "ALL", "scrolls": 10, "top": 5, "ids": [], "products": []},
    "thumbs": {"per_product": {}, "default": 200, "max_size": [300, 375]},
    "eu_reach": {"top": 100, "products": []},
}


def read_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load(path):
    cfg = read_json(path)
    out = {}
    for k, v in DEFAULTS.items():
        if isinstance(v, dict):
            out[k] = {**v, **(cfg.get(k) or {})}
        else:
            out[k] = cfg.get(k, v)
    for k, v in cfg.items():
        out.setdefault(k, v)
    base = os.path.dirname(os.path.abspath(path))
    out["_path"] = os.path.abspath(path)
    out["_dir"] = os.path.normpath(os.path.join(base, out["output_dir"]))
    out["scrape"]["parallel"] = max(1, min(int(out["scrape"]["parallel"]), MAX_PARALLEL))
    validate(out)
    return out


def validate(cfg):
    for q in cfg["queries"]:
        missing = {"cat", "country", "q"} - set(q)
        if missing:
            raise ValueError(f"заявка без {sorted(missing)}: {q}")
    for name, rx in list(cfg["categories"].items()) + list(cfg["flags"].items()):
        re.compile(rx)
    for r in cfg["products"]:
        if "product" not in r:
            raise ValueError(f"правило без product: {r}")
        for c in list(r.get("require", [])) + list(r.get("exclude", [])):
            if c not in cfg["categories"]:
                raise ValueError(f"правило {r['product']}: непозната категория {c}")


def path(cfg, *parts):
    return os.path.join(cfg["_dir"], *parts)


def slug(s):
    return re.sub(r"[ /\\]+", "_", s.strip())


def raw_name(cat, country, q=None, page_id=None):
    if page_id:
        return f"page__{country}__{page_id}.json"
    return f"{cat}__{country}__{slug(q)}.json"


def scrape_date(cfg):
    """Датата на свалянето: от run.json, иначе от raw/_meta.json, иначе днес."""
    if cfg.get("scrape_date"):
        return datetime.date.fromisoformat(cfg["scrape_date"])
    meta = path(cfg, "raw", "_meta.json")
    if os.path.exists(meta):
        d = read_json(meta).get("scrape_date")
        if d:
            return datetime.date.fromisoformat(d)
    return datetime.date.today()
