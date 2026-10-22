"""Еталонен тест: попадат ли твоите избори в топа на оценката.

    python3 agent/golden.py goldens/*.json [--k 5]

Пускай го след всяка промяна в evidence.py / fit.py / теглата. Ако „Да“ фуниите паднат от топ k, промяната е лоша.
Изход: ранг на всяка избрана фуния, дял в топ k, среден ранг. Код 1, ако делът в топ k падне под --min (по подразбиране 0.67).
"""
import argparse, json, os, sys


def rank(golden, k):
    g = json.load(open(golden))
    scored = json.load(open(os.path.expanduser(g["scored"])))
    order = [os.path.basename(f.get("folder", "").rstrip("/")) for f in scored]
    # краткият списък за избор = топ k по крайна оценка + топ 2 местни конкуренти
    shortlist = set(order[:k]) | {os.path.basename(f.get("folder", "").rstrip("/")) for f in scored if f.get("local_rank") and f["local_rank"] <= 2}
    ranks = {y: (order.index(y) + 1 if y in order else None) for y in g["funnels_yes"]}
    found = [r for r in ranks.values() if r]
    hit = sum(1 for y in g["funnels_yes"] if y in shortlist) / len(ranks)
    return dict(golden=os.path.basename(golden), n=len(order), ranks=ranks, hit_at_k=round(hit, 2),
                mean_rank=round(sum(found) / len(found), 1) if found else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("goldens", nargs="+")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--min", type=float, default=0.67)
    a = ap.parse_args()
    bad = False
    for g in a.goldens:
        r = rank(g, a.k)
        print(f"{r['golden']:24} в краткия списък (топ {a.k} + 2 местни): {r['hit_at_k']:.0%}  среден ранг {r['mean_rank']} от {r['n']}  {r['ranks']}")
        bad |= r["hit_at_k"] < a.min
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
