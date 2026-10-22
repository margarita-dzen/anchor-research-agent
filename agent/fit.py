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
WEIGHTS = dict(type=20, relevance=25, angle=20, safety=10, proof=15, market=10)
EU = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}


def market_score(f, markets):
    """1 = конкурент на нашия пазар (домейн или държави на рекламите), 0.5 = друг пазар в ЕС, 0.2 = извън ЕС."""
    if not markets:
        return 0.5
    m = {x.upper() for x in markets}
    host = re.sub(r"^https?://", "", (f.get("steps") or [{}])[0].get("url") or "").split("/")[0]
    tld = host.rsplit(".", 1)[-1].upper()
    cc = {c.upper() for c in (f.get("ad_evidence") or {}).get("countries", [])}
    if tld in m or cc & m:
        return 1.0
    if tld in EU or cc & EU:
        return 0.5
    return 0.2


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
    s["market"] = market_score(f, cfg.get("markets"))
    score = round(sum(WEIGHTS[k] * v for k, v in s.items()), 1)
    return score, {k: round(v, 2) for k, v in s.items()}, dict(angles=angles, risk_terms=risk, review_blocks_in_original=need)


def local_evidence(row, markets, min_days=90):
    """Конкурент на нашия пазар с малко реклами: ако единственият отказ е броят, а рекламата е активна,
    върви >= min_days и е в наш пазар, малката извадка в Ad Library не значи, че фунията е слаба."""
    from evidence import evidence_score
    only_count = all(r.startswith("под ") for r in row.get("rejected", []))
    local = {c.upper() for c in row.get("countries", [])} & {m.upper() for m in markets or []}
    if not (only_count and local and row.get("active_ads") and row.get("max_days", 0) >= min_days):
        return None
    sig = {k: row.get(k) for k in ("active_ads", "duplicates", "new_ads_30d", "max_days", "domain_visits")}
    sig["countries"] = len(row.get("countries", []))
    return evidence_score(sig)[0]


def funnels_mode(a):
    cfg = load_run(a.run)
    cfg.setdefault("markets", json.load(open(a.run)).get("markets"))
    fns = json.load(open(a.funnels))
    ev, rej = {}, {}
    if a.evidence:
        e = json.load(open(a.evidence))
        for r in e["passed"]:
            ev[r["url"]] = r["evidence"]
        for r in e.get("rejected", []):
            rej[r["url"]] = r
    ours = bank_proof(a.bank, cfg.get("bank_products"))
    for f in fns:
        f["fit"], f["fit_breakdown"], f["fit_notes"] = fit_score(f, cfg, ours)
        url = (f.get("steps") or [{}])[0].get("url") or ""
        u = re.sub(r"^https?://(www\.)?", "https://", url.split("?")[0]).rstrip("/")
        f["evidence"] = ev.get(u)
        f["evidence_source"] = "url"
        if f["evidence"] is None:
            # няма реклами точно към този URL: най-силният URL на същия домейн × 0.8
            host = u.split("/")[2] if u.count("/") >= 2 else ""
            same = [v for k, v in ev.items() if k.split("/")[2:3] == [host]]
            if same:
                f["evidence"], f["evidence_source"] = round(max(same) * 0.8, 1), "домейн × 0.8"
            elif u in rej:
                le = local_evidence(rej[u], cfg.get("markets"))
                if le is not None:
                    f["evidence"], f["evidence_source"] = le, "местен пазар, малка извадка"
        f["final"] = round(0.6 * f["evidence"] + 0.4 * f["fit"], 1) if f["evidence"] is not None else None
    fns.sort(key=lambda f: -(f["final"] if f["final"] is not None else f["fit"] * 0.4))
    # местните конкуренти (нашият пазар) винаги излизат в отделен списък: топ 2 от тях отиват в избора,
    # защото Ad Library вижда малко от местните реклами (еталон ATOPI: Karbonoir RO, 1 реклама от 341 дни)
    # подредени по пасване, не по сила: при местните силата е ненадеждна
    local = sorted([f for f in fns if f["fit_breakdown"]["market"] == 1.0], key=lambda f: -f["fit"])
    for i, f in enumerate(local):
        f["local_rank"] = i + 1
    json.dump(fns, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"банка: {ours}")
    if local:
        print("местни конкуренти (топ 2 винаги в избора):", ", ".join(f"{f.get('brand', '')[:24]} ({f['fit']})" for f in local[:2]))
    print(f"{'крайна':>6} {'сила':>5} {'пасв':>5}  тип  тема ъгъл безоп док  пазар фуния")
    for f in fns:
        b = f["fit_breakdown"]
        fin = f"{f['final']:6.1f}" if f["final"] is not None else "     -"
        evs = f"{f['evidence']:5.1f}" if f["evidence"] is not None else "    -"
        print(f"{fin} {evs} {f['fit']:5.1f}  {b['type']:.2f} {b['relevance']:.2f} {b['angle']:.2f} {b['safety']:.2f} {b['proof']:.2f} {b['market']:.2f}  {f.get('brand', '')[:28]}")


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
