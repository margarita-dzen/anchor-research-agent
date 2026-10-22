"""Седмично донастройване на скалата по реални продажби на нашите клонинги.

    python3 agent/calibrate.py collect runs/<x>      # results.json + clones в run.json → runs/<x>/outcomes.json
    python3 agent/calibrate.py fit runs/*/           # от всички outcomes → предложени тегла (agent/config/weights.proposed.json)
    python3 agent/calibrate.py accept | revert       # приема предложението / връща старите тегла, ако еталонът падне

run.json трябва да има "clones": {"/pages/<нашият handle>": "<URL на оригиналната фуния>"}.
Сигналите на оригинала се взимат от landing_ranked_<p>.json (или landing_evidence). ROAS е от results.py.
Правило: нужни са поне 6 клонинга с разход >= 50 в сметката на акаунта. Под това теглата не се пипат.
Промяната е наполовина: ново = старо × (1 + ρ/2), ρ = рангова корелация на сигнала с ROAS, ограничена в [-0.5, 0.5].
"""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "agent"))
from evidence import SIGNALS  # noqa: E402

MIN_N, MIN_SPEND = 6, 50
CONF = os.path.join(ROOT, "agent", "config")


def norm(u):
    return (u or "").split("?")[0].replace("http://", "https://").replace("://www.", "://").rstrip("/")


def collect(run):
    cfg = json.load(open(os.path.join(run, "run.json")))
    res = json.load(open(os.path.join(run, "results.json")))
    d = os.path.expanduser(cfg.get("data_dir", run))
    p = cfg["product"]
    ranked = next((f for f in (f"{d}/ads/landing_ranked_{p}.json", f"{d}/ads/landing_evidence_{p}.json") if os.path.exists(f)), None)
    sig = {}
    if ranked:
        e = json.load(open(ranked))
        for r in e["passed"] + e.get("rejected", []):
            sig[norm(r["url"])] = dict(active_ads=r["active_ads"], duplicates=r["duplicates"], new_ads_30d=r["new_ads_30d"],
                                       max_days=r["max_days"], countries=len(r["countries"]), domain_visits=r.get("domain_visits"))
    by = {x["key"]: x for x in res["by_landing"]}
    out = []
    for ours, src in (cfg.get("clones") or {}).items():
        r = by.get(ours)
        if not r:
            continue
        out.append(dict(ours=ours, source=src, spend=r["spend"], roas=r["roas"], signals=sig.get(norm(src))))
    json.dump(out, open(os.path.join(run, "outcomes.json"), "w"), ensure_ascii=False, indent=1)
    print(f"{len(out)} клонинга с резултати → {run}/outcomes.json")


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for pos, i in enumerate(order):
        r[i] = float(pos)
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else 0.0


def fit(runs):
    rows = []
    for r in runs:
        p = os.path.join(r, "outcomes.json")
        if os.path.exists(p):
            rows += [x for x in json.load(open(p)) if x["signals"] and x["roas"] is not None and x["spend"] >= MIN_SPEND]
    print(f"клонинги с достатъчно разход: {len(rows)} (нужни {MIN_N})")
    if len(rows) < MIN_N:
        print("рано е за донастройване, теглата остават")
        return
    roas = [x["roas"] for x in rows]
    new, rho = {}, {}
    for k, (w, _, _) in SIGNALS.items():
        vals = [x["signals"].get(k) for x in rows]
        if any(v is None for v in vals):
            new[k] = w
            continue
        rho[k] = max(-0.5, min(0.5, spearman(vals, roas)))
        new[k] = w * (1 + rho[k] / 2)
    total = sum(new.values())
    new = {k: round(100 * v / total, 1) for k, v in new.items()}
    json.dump(dict(n=len(rows), rho={k: round(v, 2) for k, v in rho.items()}, weights=new), open(os.path.join(CONF, "weights.proposed.json"), "w"), indent=1)
    print("корелация с ROAS:", {k: round(v, 2) for k, v in rho.items()})
    print("предложени тегла:", new, "→ python3 agent/calibrate.py accept")


def accept():
    """Приема предложението и пазят старите тегла. После: пусни evidence.py + fit.py за пусканията от goldens/
    и agent/golden.py. Ако еталонът падне → python3 agent/calibrate.py revert."""
    prop, cur = os.path.join(CONF, "weights.proposed.json"), os.path.join(CONF, "weights.json")
    if os.path.exists(cur):
        shutil.copy(cur, cur + ".bak")
    shutil.copy(prop, cur)
    print("приети. Сега: evidence.py + fit.py за пусканията от goldens/, после agent/golden.py goldens/*.json")


def revert():
    cur = os.path.join(CONF, "weights.json")
    if os.path.exists(cur + ".bak"):
        shutil.move(cur + ".bak", cur)
    elif os.path.exists(cur):
        os.remove(cur)
    print("върнати старите тегла")


if __name__ == "__main__":
    {"collect": lambda: collect(sys.argv[2]), "fit": lambda: fit(sys.argv[2:]), "accept": accept, "revert": revert}[sys.argv[1]]()
