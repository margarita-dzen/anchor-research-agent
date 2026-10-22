"""Отчет за kie.ai кредитите по етап, за да не свършват по средата на работата.

    python3 agent/credits.py balance [--all]               # основният ключ; --all и ключа на Маргарита (Павлова/Vitalaiz)
    python3 agent/credits.py start runs/<x> clone-art      # записва баланса преди етапа
    python3 agent/credits.py end   runs/<x> clone-art      # записва баланса след етапа и колко е изхарчено
    python3 agent/credits.py report runs/<x>               # разход по етап
    python3 agent/credits.py need 120                      # стига ли основният ключ за ~120 кредита (код 1, ако не)

Ориентири (22.10.2026): gpt-image-2 i2i 2K ≈ 15 кр., 1K ≈ 4-6 кр., 4K 1:1 = 16 кр., Kling std 5 s ≈ 70 кр.
Kie таксува и отказаните „unsafe“ опити, затова --tries 1 при рискови промптове.
"""
import datetime, json, os, re, sys, urllib.request

ENV = os.path.expanduser("~/ads-automation/.env")
# „маргарита“ = ключът, който в паметта е „ключът на Маргарита“ (Павлова/Vitalaiz, за So Simple с отчет)
KEYS = {"основен": "KIE_AI_API_KEY", "маргарита": "KIE_AI_API_KEY_PAVLOVA_VITALAIZ"}


def env():
    out = {}
    for line in open(ENV):
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def balance(key):
    req = urllib.request.Request("https://api.kie.ai/api/v1/chat/credit", headers={"Authorization": f"Bearer {key}"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    return d.get("data")


def balances(all_keys=False):
    """По подразбиране само основният ключ. Ключът на Маргарита (Павлова/Vitalaiz) се чете само с --all:
    той е за Павлова/Vitalaiz, а за други клиенти само при изрично разрешение (тест 22.10: агентът щеше да харчи от него)."""
    e = env()
    out = {}
    for name, var in KEYS.items():
        if name != "основен" and not all_keys:
            continue
        if e.get(var):
            try:
                out[name] = balance(e[var])
            except Exception as ex:
                out[name] = f"грешка: {ex}"
    return out


def ledger(run):
    return os.path.join(run, "credits.jsonl")


def log(run, event, stage):
    rec = dict(ts=datetime.datetime.now().isoformat(timespec="seconds"), event=event, stage=stage, balances=balances())
    open(ledger(run), "a").write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def report(run):
    starts, rows = {}, []
    for line in open(ledger(run)):
        r = json.loads(line)
        if r["event"] == "start":
            starts[r["stage"]] = r
        elif r["event"] == "end" and r["stage"] in starts:
            b0, b1 = starts[r["stage"]]["balances"], r["balances"]
            spent = {k: round(b0[k] - b1[k], 2) for k in b0 if isinstance(b0.get(k), (int, float)) and isinstance(b1.get(k), (int, float))}
            rows.append((r["stage"], spent, b1))
    for stage, spent, after in rows:
        print(f"{stage:20} изхарчено {spent}  остава {after}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "balance"
    if cmd == "balance":
        print(balances("--all" in sys.argv))
    elif cmd in ("start", "end"):
        print(log(sys.argv[2], cmd, sys.argv[3]))
    elif cmd == "report":
        report(sys.argv[2])
    elif cmd == "need":
        need = float(sys.argv[2])
        b = balances().get("основен")
        ok = isinstance(b, (int, float)) and b >= need
        print(f"основен ключ: {b}, нужни ~{need}: {'стига' if ok else 'НЕ СТИГА, питай за зареждане или за ключа на Маргарита'}")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
