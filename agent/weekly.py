"""Седмичният цикъл за едно пускане: конкурентите отново, кои фунии спират и кои растат, нашите резултати, донастройване.

    python3 agent/weekly.py runs/<x>/run.json [--no-scrape]

1. Снимка на сегашния ads_all.json в snapshots/<дата>/, ново сваляне със СЪЩИТЕ заявки (harvest_config), consolidate.
2. snapshot_diff срещу предишната снимка → snapshots/diff_<дата>.json (кои лендинги пускат нови реклами, кои спират).
3. results.py за последните 7 дни → runs/<x>/results.json, после calibrate.py collect.
4. feedback.py report (научените проверки).
Ограничение: сваляне само по 2 паралелно (adlib). Пускането е ръчно или по график (вж. README, „Седмично“).
"""
import datetime, glob, json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "agent")


def sh(cmd):
    print("$", cmd)
    return subprocess.run(cmd, shell=True).returncode == 0


def main():
    rj = os.path.abspath(sys.argv[1])
    run = os.path.dirname(rj)
    cfg = json.load(open(rj))
    today = datetime.date.today().isoformat()
    if "--no-scrape" not in sys.argv and cfg.get("harvest_config"):
        hc = os.path.join(ROOT, cfg["harvest_config"])
        hcfg = json.load(open(hc))
        out = os.path.normpath(os.path.join(os.path.dirname(hc), hcfg.get("output_dir", ".")))
        snaps = os.path.join(out, "snapshots")
        os.makedirs(snaps, exist_ok=True)
        cur = os.path.join(out, "ads_all.json")
        prev = sorted(glob.glob(os.path.join(snaps, "*", "ads_all.json")))
        if os.path.exists(cur):
            os.makedirs(os.path.join(snaps, today), exist_ok=True)
            shutil.copy(cur, os.path.join(snaps, today, "ads_all.before.json"))
        if sh(f"python3 {A}/adlib/harvest.py {hc}") and sh(f"python3 {A}/adlib/consolidate.py {hc}"):
            os.makedirs(os.path.join(snaps, today), exist_ok=True)
            shutil.copy(cur, os.path.join(snaps, today, "ads_all.json"))
            if prev:
                sh(f"python3 {A}/adlib/snapshot_diff.py {prev[-1]} {cur} --out {snaps}/diff_{today}.json")
            sh(f"python3 {A}/adlib/thumbs.py {hc}")
    if cfg.get("ad_account"):
        since = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        if sh(f"python3 {A}/results.py --account {cfg['ad_account']} --since {since} --until {today} --match {cfg['product']} --out {run}/results.json"):
            sh(f"python3 {A}/calibrate.py collect {run}")
    sh(f"python3 {A}/calibrate.py fit {os.path.join(ROOT, 'runs')}/*/")
    sh(f"python3 {A}/feedback.py report {os.path.join(ROOT, 'runs')}/*/")


if __name__ == "__main__":
    main()
