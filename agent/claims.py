"""Проверка на „№1“ и „недостиг“ по истинските продажби в Shopify (absolute-clone.md §8.2). Само четене, магазинът не се променя.

    python3 agent/claims.py rank  --product-title "ACNE GONE" --peers "Чай при Акне" [--client so_simple] [--days 90]
    python3 agent/claims.py stock --handle acne-gone-mehlem-pri-akne [--client so_simple] [--days 90]

rank:  ShopifyQL продажби по продукт за последните N дни → мястото на продукта сред всички и сред конкурентите
       му в магазина за същия проблем (--peers, части от заглавия, разделени със запетая) → дали „№1 при <проблем>“ е вярно.
stock: totalInventory + продадени бройки за N дни → седмици наличност и честна формулировка
       („ограничено количество“ само под LIMITED_WEEKS седмици).
Shopify: so_simple (helper-ът _lib.mjs с gql от ads-automation). Python пише временен .mjs и пуска node.
WooCommerce: nordics (23.10). Продажбите от wc-analytics/reports/products, наличността от wc/v3/products?slug=.
Достъпът е WP application password „user:pass“ от env WP_AUTH_<КЛИЕНТ> или ~/.config/anchor-research-agent/wp_<клиент>
(никога в репото). За Woo --handle е slug-ът на продукта.
"""
import argparse, base64, datetime, json, os, subprocess, sys, tempfile, urllib.parse, urllib.request

LIBS = {"so_simple": "/Users/magi/ads-automation/clients/so_simple/shopify/_lib.mjs"}
WOO = {"nordics": "https://wearenordics.com"}
LIMITED_WEEKS = 10

NODE = """import { gql } from %s;
const [query, vars] = JSON.parse(process.argv[2]);
const r = await gql(query, vars);
process.stdout.write(JSON.stringify(r));
"""


def gql(client, query, variables=None):
    """Пуска една GraphQL заявка през node + _lib.mjs на клиента. Само заявки за четене."""
    if client not in LIBS:
        raise SystemExit(f"claims.py: клиентът {client} не е вързан (има: {', '.join(LIBS)}). Добави _lib.mjs в LIBS.")
    if query.lstrip().startswith("mutation"):
        raise SystemExit("claims.py е само за четене")
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
        fh.write(NODE % json.dumps(LIBS[client]))
        path = fh.name
    try:
        p = subprocess.run(["node", path, json.dumps([query, variables or {}])], capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(path)
    if p.returncode:
        raise SystemExit("Shopify заявката не мина:\n" + p.stderr[-1500:])
    return json.loads(p.stdout)


def shopifyql(client, q):
    d = gql(client, "query($q:String!){shopifyqlQuery(query:$q){tableData{columns{name} rows} parseErrors}}", {"q": q})["shopifyqlQuery"]
    if d.get("parseErrors"):
        raise SystemExit(f"ShopifyQL грешка: {d['parseErrors']}")
    return d["tableData"]["rows"]


def woo_auth(client):
    v = os.environ.get(f"WP_AUTH_{client.upper()}")
    f = os.path.expanduser(f"~/.config/anchor-research-agent/wp_{client}")
    if not v and os.path.exists(f):
        v = open(f).read().strip()
    if not v:
        raise SystemExit(f"няма достъп до WooCommerce за {client}: env WP_AUTH_{client.upper()} или {f} (user:application password)")
    return "Basic " + base64.b64encode(v.encode()).decode()


def woo_get(client, path, params=None):
    """Само GET към WooCommerce REST."""
    url = f"{WOO[client]}/wp-json/{path}" + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": woo_auth(client), "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def woo_sales(client, days):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    rows, page = [], 1
    while True:
        d = woo_get(client, "wc-analytics/reports/products", dict(after=f"{start}T00:00:00", before=f"{end}T23:59:59", per_page=100,
                                                                  page=page, orderby="items_sold", order="desc", extended_info="true"))
        rows += [dict(title=(x.get("extended_info") or {}).get("name") or str(x["product_id"]), units=float(x.get("items_sold") or 0),
                      net=float(x.get("net_revenue") or 0), id=x["product_id"]) for x in d]
        if len(d) < 100:
            return rows
        page += 1


def sales(client, days):
    if client in WOO:
        return woo_sales(client, days)
    q = (f"FROM sales SHOW net_items_sold, net_sales GROUP BY product_title SINCE -{days}d UNTIL today "
         "ORDER BY net_items_sold DESC LIMIT 1000")
    return [dict(title=r["product_title"], units=float(r["net_items_sold"] or 0), net=float(r["net_sales"] or 0)) for r in shopifyql(client, q)]


def real_products(rows):
    """Без редове без заглавие и без подаръци (нула приход): те не са продукти, които клиентът продава."""
    return sorted([r for r in rows if r["title"] and r["net"] > 0], key=lambda r: -r["units"])


def rank(rows, title, peers):
    """Връща (продуктът, място сред всички, място сред продукта + конкурентите, списък конкуренти)."""
    rows = real_products(rows)
    t = title.lower()
    own = [r for r in rows if t in r["title"].lower()]
    if not own:
        return None, None, None, []
    me = own[0]
    group = [r for r in rows if r is me or any(p.strip() and p.strip().lower() in r["title"].lower() for p in peers)]
    return me, rows.index(me) + 1, group.index(me) + 1, group


def stock_wording(inventory, units, days):
    weekly = units / (days / 7) if days else 0
    weeks = inventory / weekly if weekly else None
    months = round(days / 30)
    sold = int(units // 100 * 100) if units >= 100 else int(units)
    lines = [f"Голямо търсене: над {sold:,} продадени за {months} месеца".replace(",", " ")]
    if weeks is not None and weeks < LIMITED_WEEKS:
        lines.append("Ограничено количество (наличността стига за под %d седмици)" % LIMITED_WEEKS)
    return weekly, weeks, lines


def cmd_rank(a):
    me, overall, among, group = rank(sales(a.client, a.days), a.product_title, a.peers.split(",") if a.peers else [])
    if not me:
        raise SystemExit(f"няма продажби за заглавие с „{a.product_title}“ за {a.days} дни")
    print(f"Продажби за {a.days} дни (без подаръци и редове без продукт):")
    for i, r in enumerate(group, 1):
        print(f"  {i}. {r['title']}: {int(r['units'])} бр., {r['net']:.0f} €")
    print(f"„{me['title']}“: №{overall} сред всички продукти, №{among} от {len(group)} сред продуктите за същия проблем.")
    if among == 1:
        print(f"„№1 при <проблем>“: ДА (най-продаваният в магазина за проблема, {a.days} дни, {'wc-analytics' if a.client in WOO else 'ShopifyQL'}).")
    else:
        print("„№1 при <проблем>“: НЕ. Пиши друго („любим на купувачите“, броя продажби).")
    if overall == 1:
        print("„№1 продукт на марката“: ДА.")


def cmd_stock_woo(a):
    found = woo_get(a.client, "wc/v3/products", dict(slug=a.handle))
    if not found:
        raise SystemExit(f"няма продукт със slug {a.handle}")
    p = found[0]
    row = next((r for r in sales(a.client, a.days) if r["id"] == p["id"]), None)
    units = row["units"] if row else 0
    print(f"„{p['name']}“ ({p['id']}): продадени {int(units)} за {a.days} дни, total_sales за цялото време {p.get('total_sales')}")
    if not p.get("manage_stock"):
        print("Магазинът не следи бройки (manage_stock: false): недостигът НЕ е проверим по данни.")
        note = (json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "clients.json"))).get(a.client, {}).get("claims") or {}).get("low_stock_text")
        if note:
            print(f"Одобрена от Валентин формулировка: „{note}“ (без бройки).")
        print("Честни формулировки:")
        print(f"  - " + stock_wording(0, units, a.days)[2][0])
        return
    weekly, weeks, lines = stock_wording(p.get("stock_quantity") or 0, units, a.days)
    print(f"Наличност {p.get('stock_quantity')} бр. ({weekly:.0f} на седмица), стига за {weeks:.1f} седмици" if weeks else f"Наличност {p.get('stock_quantity')} бр.")
    print("Честни формулировки:")
    for x in lines:
        print("  - " + x)


def cmd_stock(a):
    if a.client in WOO:
        return cmd_stock_woo(a)
    p = gql(a.client, "query($h:String!){productByHandle(handle:$h){title totalInventory}}", {"h": a.handle})["productByHandle"]
    if not p:
        raise SystemExit(f"няма продукт {a.handle}")
    row = next((r for r in sales(a.client, a.days) if r["title"] == p["title"]), None)
    units = row["units"] if row else 0
    weekly, weeks, lines = stock_wording(p["totalInventory"], units, a.days)
    print(f"„{p['title']}“: наличност {p['totalInventory']} бр., продадени {int(units)} за {a.days} дни ({weekly:.0f} на седмица)")
    print(f"Стига за: {weeks:.1f} седмици" if weeks is not None else "Стига за: няма продажби, не се смята")
    print("Честни формулировки:")
    for x in lines:
        print("  - " + x)
    if weeks is None or weeks >= LIMITED_WEEKS:
        print(f"  („ограничено количество“ НЕ: наличността стига за >= {LIMITED_WEEKS} седмици)")


def main():
    ap = argparse.ArgumentParser(description="№1 и недостиг по продажбите в Shopify / WooCommerce (само четене)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank")
    r.add_argument("--product-title", required=True)
    r.add_argument("--peers", default="", help="части от заглавия на продуктите за същия проблем, разделени със запетая")
    s = sub.add_parser("stock")
    s.add_argument("--handle", required=True)
    for x in (r, s):
        x.add_argument("--client", default="so_simple")
        x.add_argument("--days", type=int, default=90)
    a = ap.parse_args()
    {"rank": cmd_rank, "stock": cmd_stock}[a.cmd](a)


if __name__ == "__main__":
    main()
