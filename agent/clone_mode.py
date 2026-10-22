"""Дизайн режим при клониране: бранд бука на клиента или дизайнът на примера.

Правило (Валентин, 22.10.2026):
  - лендингът е на основния домейн на магазина (същият хост като PDP/количката) → "brand":
    структурата 1:1, цветове/шрифтове/бутони от бранд бука и сайта на клиента;
  - лендингът е на друг хост (трета медия, лична история, поддомейн-пресейл като go./learn./try./continut.) → "keep":
    цветовете, шрифтовете и дизайнът на примера се запазват.

    python3 agent/clone_mode.py funnels_acne.json
"""
import json, sys
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


def main():
    for f in json.load(open(sys.argv[1])):
        mode, why = clone_mode(f.get("steps") or [])
        print(f"{mode:5}  {f.get('brand', '')[:22]:22}  {why}")


if __name__ == "__main__":
    main()
