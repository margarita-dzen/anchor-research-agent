"""Дизайн режим при клониране: бранд бука на клиента или дизайнът на примера.

Правило (Валентин, 22.10.2026):
  - лендингът е на основния домейн на магазина (същият хост като PDP/количката) → "brand":
    структурата 1:1, цветове/шрифтове/бутони от бранд бука и сайта на клиента;
  - лендингът е на друг хост (трета медия, лична история, поддомейн-пресейл като go./learn./try./continut.) → "keep":
    цветовете, шрифтовете и дизайнът на примера се запазват.

    python3 agent/clone_mode.py funnels_acne.json [--client nordics]

Клиентът може да има `clone_overrides` в config/clients.json (Nordics 23.10: шрифтове и цветове винаги от бранд бука,
без курсив, бутони с главни букви). Те важат и в режим keep: от примера остават структурата и техниките.
"""
import json, os, sys
from urllib.parse import urlparse

STORE_TYPES = {"PDP", "bundle", "cart"}


def host(u):
    return urlparse((u or "").split(" ")[0]).netloc.lower().removeprefix("www.")


def clone_mode(steps):
    """steps: [{type, url}] в реда на фунията. Връща (режим, причина)."""
    if not steps:
        return "keep", "няма стъпки"
    land = host(steps[0].get("url"))
    store = [host(s.get("url")) for s in steps[1:] if s.get("type") in STORE_TYPES and s.get("url")]
    if not store:
        if steps[0].get("type") in STORE_TYPES:
            return "brand", "лендингът е страница от магазина"
        return "keep", "не стига до магазин, няма как да се докаже, че е на основния домейн"
    if land == store[0]:
        return "brand", f"на основния домейн на магазина ({land})"
    return "keep", f"външен хост {land}, магазинът е на {store[0]}"


def overrides(client, path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "clients.json")):
    o = (json.load(open(path)).get(client) or {}).get("clone_overrides") or {}
    return {k: v for k, v in o.items() if not k.startswith("_")}


def main():
    client = sys.argv[sys.argv.index("--client") + 1] if "--client" in sys.argv else None
    ov = overrides(client) if client else {}
    for f in json.load(open(sys.argv[1])):
        mode, why = clone_mode(f.get("steps") or [])
        if mode == "keep" and ov:
            why += " · но " + ", ".join(f"{k}={v}" for k, v in ov.items()) + " (clone_overrides)"
        print(f"{mode:5}  {f.get('brand', '')[:22]:22}  {why}")


if __name__ == "__main__":
    main()
