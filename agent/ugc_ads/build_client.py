#!/usr/bin/env python3
"""Документ за клиента: по лендинг -> карта на лендинга + 10 реклами като пост във фийда + „Копирай текстовете“.
Пише <root>/client.html. Публикува се като Artifact с root=<root> (визии, cmp/ снимки и лендингите в files,
на партиди под 64MB). Брандът (цветове, шрифтове, футър) е в client_tpl.html: за друг клиент смени токените там.

  python3 build_client.py <ugc.json>
ugc.json lps.<П>: folder, slug, kind (кратко име), angle (едно изречение); client.brand, client.avatar, client.campaign_utm.
"""
import html, json, os, re, sys

CFG = json.load(open(sys.argv[1]))
R = os.path.expanduser(CFG['root']).rstrip('/') + '/'
D = os.path.expanduser(CFG['ads_dir'])
C = CFG['client']
SITE = CFG['site']['base']
HERE = os.path.dirname(os.path.abspath(__file__))


def h1(folder):
    t = open(R + folder + '/index.html', encoding='utf-8').read()
    m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', t)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(1))).replace('&nbsp;', ' ').replace(' .', '.').strip().split(' (')[0]


def parse(pre):
    t = open(os.path.join(D, 'copy', f'{pre}.md'), encoding='utf-8').read()
    out = []
    for b in re.split(r'\n(?=## )', t)[1:]:
        code = b.split('\n', 1)[0][3:].split(' · ')[0].strip()
        ang = re.search(r'Angle:\s*([^|]+)', b)
        body = b.split('**CTA:**', 1)[1].split('\n', 1)[1].split('\n---')[0].strip()
        out.append(dict(code=code, angle=ang.group(1).strip() if ang else '', body=body,
                        hl=re.search(r'\*\*Хедлайн:\*\*\s*(.+)', b).group(1).strip(),
                        ds=re.search(r'\*\*Описание:\*\*\s*(.+)', b).group(1).strip()))
    return out


def fmt_body(body):
    e = html.escape(body)
    e = re.sub(re.escape(SITE) + r'/lp/[a-z0-9-]+/\?\S+',
               lambda m: f'<a href="{m.group(0)}" target="_blank" rel="noopener">{m.group(0).split("?")[0].split("://")[1]}</a>', e)
    return '<p>' + '</p><p>'.join(x.replace('\n', '<br>') for x in e.split('\n\n')) + '</p>'


sections, nav = [], []
for pre, lp in CFG['lps'].items():
    ads = parse(pre)
    href = f"{SITE}/lp/{lp['slug']}/"
    cards = [f'''<article class="ad" id="{a['code']}">
  <div class="post">
    <header class="ph"><img class="av" src="{C['avatar']}" alt=""><div><b>{html.escape(C['brand'])}</b><small>Спонсорирано</small></div></header>
    <div class="txt">{fmt_body(a['body'])}</div>
    <img class="vis" src="{os.path.relpath(D, R)}/final/{a['code']}.jpg" alt="UGC визия {a['code']}" loading="lazy" width="1080" height="1350">
    <footer class="pf"><div class="pfl"><small>{SITE.split('://')[1].upper()}</small><b>{html.escape(a['hl'])}</b><span>{html.escape(a['ds'])}</span></div><span class="btn">Пазарувай</span></footer>
  </div>
  <div class="meta"><span class="code">{a['code']}</span><span class="ang">{html.escape(a['angle'])}</span>
    <button type="button" class="cp" data-t="{html.escape(json.dumps(dict(h=a['hl'], d=a['ds'], b=a['body']), ensure_ascii=False))}">Копирай текстовете</button></div>
</article>''' for a in ads]
    nav.append(f'<a href="#{pre}">{lp["kind"]}</a>')
    sections.append(f'''<section class="lp" id="{pre}">
  <div class="lphead">
    <a class="thumb" href="{href}" target="_blank" rel="noopener"><img src="cmp/{lp['folder']}_c.jpg" alt="Началото на лендинга" loading="lazy"></a>
    <div class="lpinfo"><span class="eyebrow">Лендинг · {lp['kind']} · реклами {pre}01-{pre}{len(ads):02d}</span>
      <h2>{html.escape(h1(lp['folder']))}</h2><p>{html.escape(lp['angle'])}</p>
      <a class="open" href="{href}" target="_blank" rel="noopener">Отвори лендинга</a>
      <p class="utm">UTM: utm_campaign={C['campaign_utm'].format(pre=pre)} · utm_content = кодът на рекламата</p></div>
  </div>
  <div class="grid">{''.join(cards)}</div>
</section>''')
tpl = open(os.path.join(HERE, 'client_tpl.html'), encoding='utf-8').read()
open(R + 'client.html', 'w', encoding='utf-8').write(tpl.replace('<!--NAV-->', ''.join(nav)).replace('<!--SECTIONS-->', ''.join(sections)))
print('ok', R + 'client.html')
