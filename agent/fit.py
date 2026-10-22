"""Оценка „пасва ли ни“ (fit, 0-100) и крайна оценка = 60% сила + 40% пасване.

Два режима:
  1. relevance  : преди снимките. Чисти класирането от evidence.py от теми извън продукта
                  (колаген за кучета в ATOPI) по текстовете на рекламите.
       python3 agent/fit.py relevance landing_evidence.json ads_all.json --run runs/<x>/run.json --out landing_ranked.json
  2. funnels    : след снимките (funnels_<p>.json + stepN_390.txt). Пълна оценка по 5 критерия.
       python3 agent/fit.py funnels funnels_acne.json --run runs/<x>/run.json --evidence landing_ranked.json \
           --bank ~/Clients/So-Simple/reviews/bank.json --out funnels_scored.json

Конфигурацията е в ключа "fit" на run.json:
  "fit": {
    "topic": "регулярен израз за темата (задължителен за relevance)",
    "exclude": "теми, които изключват реклама въпреки думите за темата (кучета, коса...)",
    "form": "форма на продукта (мехлем|балсам|стик|balm|salbe...)",
    "audience": "аудитория (майка|дете|тийнейджър|mum|teen...)",
    "angles": {"име на ъгъла": "регулярен израз", ...},
    "bank_products": ["handle на продукта в банката с отзиви", ...]
  }
"""
import argparse, json, os, re

TYPE_SCORE = {"advertorial": 1.0, "listicle": 1.0, "quiz": 0.9, "LP": 0.7, "bundle": 0.45, "PDP": 0.4, "cart": 0.0}
# медицински и рискови твърдения на няколко езика: колкото повече, толкова повече трябва да махнем
RISK = (r"\bcure[ds]?\b|\bheal(s|ed|ing)?\b|\btreat(s|ed|ment)?\b|steroid|cortiso|accutane|isotretinoin|antibiotic|"
        r"heilt|heilung|behandl|guérit|traite|vindec|tratament|лекува|излекув|стероид|лечени|"
        r"\b\d{2,3}\s?% (success|of users|erfolg)|clinically proven|klinisch|doctor recommended|dermatologist recommended")
REVIEW_HINT = r"★|⭐|verified (buyer|purchase)|„[^“]{20,300}“|\"[^\"]{20,300}\"\s*[-—–]\s*[A-ZА-Я]"
WEIGHTS = dict(type=25, relevance=25, angle=20, safety=15, proof=15)


def rx(p):
    return re.compile(p, re.I) if p else None


def hits(pattern, text):
    return len(pattern.findall(text)) if pattern and text else 0


def load_run(path):
    return json.load(open(path)).get("fit", {}) if path else {}


def relevance_mode(a):
    cfg = load_run(a.run)
    topic, form, excl = rx(cfg.get("topic")), rx(cfg.get("form")), rx(cfg.get("exclude"))
    if not topic:
        raise SystemExit("run.json → fit.topic липсва")
    ads = {x["meta_ad_id"]: x for x in json.load(open(a.ads))}
    ev = json.load(open(a.evidence))
    for r in ev["passed"]:
        texts = [f"{ads[i].get('headline') or ''} {ads[i].get('primary_text') or ''}" for i in r.get("ad_ids", []) if i in ads]
        n = len(texts) or 1
        r["topic_share"] = round(sum(bool(topic.search(t)) and not (excl and excl.search(t)) for t in texts) / n, 2)
        r["form_share"] = round(sum(bool(form.search(t)) for t in texts) / n, 2) if form else None
        r["relevant"] = r["topic_share"] >= a.min_share
    ev["passed"].sort(key=lambda r: (not r["relevant"], -r["evidence"]))
    json.dump(ev, open(a.out, "w"), ensure_ascii=False, indent=1)
    rel = [r for r in ev["passed"] if r["relevant"]]
    print(f"по темата: {len(rel)} от {len(ev['passed'])}")
    for r in rel[:a.top]:
        print(f"{r['evidence']:5.1f}  тема {r['topic_share']:.0%}  {r['url'][:90]}")
    out = [r for r in ev["passed"] if not r["relevant"]][:10]
    if out:
        print("извън темата (примери):", ", ".join(r["domain"] for r in out))


def funnel_text(f):
    t = []
    for s in f.get("steps", []):
        p = s.get("text_dump")
        if p and os.path.exists(p):
            t.append(open(p, errors="ignore").read())
        t.append(" ".join([s.get("headline") or ""] + list(s.get("sections") or [])))
    return "\n".join(t + [f.get("angle") or "", f.get("tech") or ""])


def bank_proof(bank_path, products):
    if not bank_path or not os.path.exists(os.path.expanduser(bank_path)):
        return None
    bank = json.load(open(os.path.expanduser(bank_path)))
    rows = [r for r in bank if not products or r.get("product") in products]
    return dict(reviews=len(rows), media=sum(bool(r.get("pictures") or r.get("videos")) for r in rows))


def fit_score(f, cfg, ours):
    text = funnel_text(f)
    first = (f.get("steps") or [{}])[0]
    s = {}
    s["type"] = TYPE_SCORE.get(first.get("type"), 0.5)
    topic, form, aud = rx(cfg.get("topic")), rx(cfg.get("form")), rx(cfg.get("audience"))
    s["relevance"] = min(1.0, (min(hits(topic, text), 10) / 10) * 0.5 + (min(hits(form, text), 5) / 5) * 0.3 + (min(hits(aud, text), 5) / 5) * 0.2)
    angles = {k: hits(rx(v), text) for k, v in (cfg.get("angles") or {}).items()}
    s["angle"] = min(1.0, sum(1 for v in angles.values() if v) / 2) if angles else 0.5
    risk = hits(rx(RISK), text)
    s["safety"] = max(0.0, 1 - risk / 15)
    # колко отзивни блока има оригиналът срещу колко истински имаме: снимките тежат 60%, текстовете 40%
    need = max(3, len(re.findall(REVIEW_HINT, text)))
    s["proof"] = 0.5 if ours is None else 0.6 * min(1.0, ours["media"] / need) + 0.4 * min(1.0, ours["reviews"] / (need * 3))
    score = round(sum(WEIGHTS[k] * v for k, v in s.items()), 1)
    return score, {k: round(v, 2) for k, v in s.items()}, dict(angles=angles, risk_terms=risk, review_blocks_in_original=need)


def funnels_mode(a):
    cfg = load_run(a.run)
    fns = json.load(open(a.funnels))
    ev = {}
    if a.evidence:
        for r in json.load(open(a.evidence))["passed"]:
            ev[r["url"]] = r["evidence"]
    ours = bank_proof(a.bank, cfg.get("bank_products"))
    for f in fns:
        f["fit"], f["fit_breakdown"], f["fit_notes"] = fit_score(f, cfg, ours)
        url = (f.get("steps") or [{}])[0].get("url") or ""
        u = re.sub(r"^https?://(www\.)?", "https://", url.split("?")[0]).rstrip("/")
        f["evidence"] = ev.get(u)
        f["final"] = round(0.6 * f["evidence"] + 0.4 * f["fit"], 1) if f["evidence"] is not None else None
    fns.sort(key=lambda f: -(f["final"] if f["final"] is not None else f["fit"] * 0.4))
    json.dump(fns, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"банка: {ours}")
    print(f"{'крайна':>6} {'сила':>5} {'пасв':>5}  тип  тема ъгъл безоп док  фуния")
    for f in fns:
        b = f["fit_breakdown"]
        fin = f"{f['final']:6.1f}" if f["final"] is not None else "     -"
        evs = f"{f['evidence']:5.1f}" if f["evidence"] is not None else "    -"
        print(f"{fin} {evs} {f['fit']:5.1f}  {b['type']:.2f} {b['relevance']:.2f} {b['angle']:.2f} {b['safety']:.2f} {b['proof']:.2f}  {f.get('brand', '')[:28]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("relevance")
    r.add_argument("evidence"); r.add_argument("ads"); r.add_argument("--run", required=True); r.add_argument("--out", required=True)
    r.add_argument("--min-share", type=float, default=0.3); r.add_argument("--top", type=int, default=20)
    f = sub.add_parser("funnels")
    f.add_argument("funnels"); f.add_argument("--run", required=True); f.add_argument("--evidence"); f.add_argument("--bank")
    f.add_argument("--out", required=True)
    a = ap.parse_args()
    relevance_mode(a) if a.mode == "relevance" else funnels_mode(a)


if __name__ == "__main__":
    main()
