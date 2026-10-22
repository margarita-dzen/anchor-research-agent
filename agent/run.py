"""Едно пускане от run.json до прегледа, с 2 контролни точки за избор.

    python3 agent/run.py runs/<x>/run.json            # показва етапите и състоянието
    python3 agent/run.py runs/<x>/run.json next       # пуска следващия автоматичен етап или казва какво да направи Claude
    python3 agent/run.py runs/<x>/run.json done <етап>  # отбелязва ръчен етап / контролна точка като минали

Типове етапи:
  auto        = скрипт, пуска се директно
  claude      = прави го Claude (подагент или в разговора) по посочения документ
  checkpoint  = спира, докато Валентин не избере (артефакт за избор / преглед)
Състоянието е в runs/<x>/state.json. Кредитите на kie се записват около етапите с генерации (agent/credits.py).
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "agent")


def stages(cfg, run_dir):
    d = os.path.expanduser(cfg.get("data_dir", run_dir))
    p = cfg["product"]
    ads = os.path.expanduser(cfg.get("ads", f"{d}/ads/ads_all.json"))
    prod = " ".join(f"--product {x}" for x in cfg.get("evidence_products", [p]))
    rj = os.path.join(run_dir, "run.json")
    hc = os.path.join(ROOT, cfg["harvest_config"]) if cfg.get("harvest_config") else rj  # конфигурацията на adlib (заявки, теми)
    bank = os.path.expanduser(cfg.get("bank", f"~/Clients/{cfg.get('client_dir', '')}/reviews/bank.json"))
    return [
        ("harvest", "auto", f"python3 {A}/adlib/harvest.py {hc} && python3 {A}/adlib/harvest.py {hc} --top-pages 5", "Сваляне на рекламите от Ad Library по run.json (queries)"),
        ("consolidate", "auto", f"python3 {A}/adlib/consolidate.py {hc} && python3 {A}/adlib/thumbs.py {hc} && python3 {A}/adlib/eu_reach.py {hc} --top 100", "Обединяване по collation_id, визии"),
        ("evidence", "auto", f"python3 {A}/evidence.py {ads} {prod} --out {d}/ads/landing_evidence_{p}.json", "Сила на доказателствата"),
        ("relevance", "auto", f"python3 {A}/fit.py relevance {d}/ads/landing_evidence_{p}.json {ads} --run {rj} --out {d}/ads/landing_ranked_{p}.json", "Чистене от теми извън продукта"),
        ("reviews", "auto", cfg.get("reviews_build", ""), "Банка с истински отзиви на клиента"),
        ("angles", "claude", "docs/stages.md#ъгли", "Ъгли и хукове от рекламите + банката (creative-strategy, copy-masters/schwartz)"),
        ("funnels", "claude", "docs/stages.md#фунии", "Снимки и разбор на топ 10-14 фунии от landing_ranked (само relevant)"),
        ("fit", "auto", f"python3 {A}/fit.py funnels {d}/funnels/funnels_{p}.json --run {rj} --evidence {d}/ads/landing_ranked_{p}.json --bank {bank} --out {d}/funnels/funnels_{p}_scored.json", "Пасване + крайна оценка"),
        ("pick", "checkpoint", "docs/stages.md#избор", "КОНТРОЛНА ТОЧКА 1: артефакт Да/Може би/Не за ъгли, хукове, фунии"),
        ("clone", "claude", "docs/absolute-clone.md", "Клониране на избраните фунии (clone_mode.py решава дизайна)"),
        ("copy", "claude", "skills/copy-masters/SKILL.md", "Текстове за страниците и рекламите, авторът в utm_content"),
        ("ads", "claude", "docs/stages.md#реклами", "Визии (anchor-creative-playbook), kie кредити през credits.py start/end"),
        ("qa", "claude", "docs/absolute-clone.md#7", f"За всеки клонинг: python3 {A}/qa/run_qa.py <оригинал> <клонинг> --client {cfg.get('client')} --out {run_dir}/qa/<фуния>"),
        ("review", "checkpoint", "templates/review/README.md", "КОНТРОЛНА ТОЧКА 2: преглед и одобрение (Shelly шаблоните)"),
        ("results", "auto", f"python3 {A}/results.py --account {cfg.get('ad_account', '?')} --since {{since}} --until {{until}} --match {p} --out {run_dir}/results.json", "След 7-14 дни: ROAS по фуния, концепция, автор"),
    ]


def load_state(run_dir):
    p = os.path.join(run_dir, "state.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def save_state(run_dir, st):
    json.dump(st, open(os.path.join(run_dir, "state.json"), "w"), ensure_ascii=False, indent=1)


def main():
    rj = sys.argv[1]
    run_dir = os.path.dirname(os.path.abspath(rj))
    cfg = json.load(open(rj))
    st = load_state(run_dir)
    ss = stages(cfg, run_dir)
    cmd = sys.argv[2] if len(sys.argv) > 2 else "status"
    if cmd == "done":
        if sys.argv[3] == "qa" and "--force" not in sys.argv:
            # прагът: до прегледа стига само клонинг с вердикт ГОТОВО или с ръчно записана причина ("accepted": "...") в qa.json
            import glob
            reps = glob.glob(os.path.join(run_dir, "qa", "*", "qa.json"))
            bad = [r for r in reps if not (json.load(open(r)).get("ready") or json.load(open(r)).get("accepted"))]
            if not reps or bad:
                print("QA не минава:", "няма отчети" if not reps else ", ".join(os.path.basename(os.path.dirname(b)) for b in bad))
                print('поправи и пусни отново, или запиши в qa.json "accepted": "<защо разликата е нарочна>"')
                return
        st[sys.argv[3]] = "done"
        save_state(run_dir, st)
        print("отбелязано:", sys.argv[3])
        return
    if cmd == "status":
        for name, kind, _, desc in ss:
            print(f"{'✓' if st.get(name) == 'done' else '·'} {name:12} {kind:10} {desc}")
        return
    for name, kind, action, desc in ss:
        if st.get(name) == "done":
            continue
        print(f"→ {name} ({kind}): {desc}")
        if kind == "auto":
            if not action or "{since}" in action:
                print("  нужни са параметри/настройка в run.json:", action or "(празно)")
                return
            r = subprocess.run(action, shell=True)
            if r.returncode == 0:
                st[name] = "done"
                save_state(run_dir, st)
                print(f"  готово. Следващ: python3 agent/run.py {rj} next")
            else:
                print("  грешка, етапът не е отбелязан")
        else:
            print(f"  направи го по {os.path.join(ROOT, action.split('#')[0])}" + (f" (секция {action.split('#')[1]})" if "#" in action else ""))
            print(f"  после: python3 agent/run.py {rj} done {name}")
        return
    print("всички етапи са минали")


if __name__ == "__main__":
    main()
