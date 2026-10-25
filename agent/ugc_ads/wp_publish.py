#!/usr/bin/env python3
"""Публикува клонингите като скрити страници <site>/lp/<slug>/ на WordPress (Nordics 25.10.2026).

Стъпки: build (dist с абсолютни пътища към assets) -> zip -> качване като медия ->
single-use снипет, който разархивира в uploads/anchor-lp/<slug>/ -> глобален снипет,
който сервира /lp/<slug>/ с noindex. Страниците не са в менюта, sitemap или търсачки.

  python3 wp_publish.py <ugc.json> build|upload|extract [slug…]|route|check
Изисква плъгина Code Snippets (REST code-snippets/v1). Ключът (user:app password) е във файла от
ugc.json site.auth_file или в env WP_AUTH, никога в репото.
Капан: extract на всичките наведнъж гърми с 500 (таймаут на PHP); пускай по един slug, проверката после е check.
"""
import json, os, re, shutil, subprocess, sys, time, urllib.request

CFG = json.load(open(sys.argv[1]))
ROOT = os.path.expanduser(CFG['root'])
SITE = CFG['site']['base']
WORK = os.path.join(os.path.expanduser(CFG['ads_dir']), 'site')
LPS = {k: (v['folder'], v['slug']) for k, v in CFG['lps'].items()}
BASE = '/wp-content/uploads/anchor-lp/'
STATE = os.path.join(WORK, 'state.json')


def auth():
    a = os.environ.get('WP_AUTH')
    if not a and CFG['site'].get('auth_file'):
        a = open(os.path.expanduser(CFG['site']['auth_file'])).read().strip()
    if not a:
        sys.exit('няма WP достъп: site.auth_file или WP_AUTH')
    return a


def curl(args):
    out = subprocess.run(['curl', '-s', '-u', auth(), '-A', 'Mozilla/5.0'] + args, capture_output=True, text=True).stdout
    return json.loads(out)


def state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save(s):
    json.dump(s, open(STATE, 'w'), indent=1, ensure_ascii=False)


def build():
    for k, (folder, slug) in LPS.items():
        dst = os.path.join(WORK, 'dist', slug)
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(os.path.join(ROOT, folder, 'assets'), os.path.join(dst, 'assets'),
                        ignore=shutil.ignore_patterns('.DS_Store'))
        h = open(os.path.join(ROOT, folder, 'index.html'), encoding='utf8').read()
        h = re.sub(r'''(["'(])assets/''', lambda m: m.group(1) + BASE + slug + '/assets/', h)
        if 'name="robots"' not in h:
            h = h.replace('<head>', '<head><meta name="robots" content="noindex, nofollow">', 1)
        open(os.path.join(dst, 'index.html'), 'w', encoding='utf8').write(h)
        z = os.path.join(WORK, f'anchorlp-{slug}.zip')
        if os.path.exists(z):
            os.remove(z)
        subprocess.run(['zip', '-qr', '-X', z, '.'], cwd=dst, check=True)
        print(k, slug, os.path.getsize(z) // 1024 // 1024, 'MB')


def upload():
    s = state()
    for k, (folder, slug) in LPS.items():
        z = os.path.join(WORK, f'anchorlp-{slug}.zip')
        r = curl(['-X', 'POST', SITE + '/wp-json/wp/v2/media', '-H', f'Content-Disposition: attachment; filename=anchorlp-{slug}-{int(time.time())}.zip',
                  '-H', 'Content-Type: application/zip', '--data-binary', '@' + z])
        print(k, r.get('id'), r.get('source_url') or r)
        s.setdefault('media', {})[slug] = r['id']
        save(s)


def snippet(name, code, scope):
    return curl(['-X', 'POST', SITE + '/wp-json/code-snippets/v1/snippets', '-H', 'Content-Type: application/json',
                 '--data-binary', json.dumps({'name': name, 'code': code, 'scope': scope, 'active': True})])


def extract():
    s = state()
    only = sys.argv[3:] or list(s['media'])
    pairs = ','.join(f"'{slug}'=>{mid}" for slug, mid in s['media'].items() if slug in only)
    code = f"""@set_time_limit(0); $base = WP_CONTENT_DIR . '/uploads/anchor-lp/';
foreach ([{pairs}] as $slug => $mid) {{
  $f = get_attached_file($mid); if (!$f || !file_exists($f)) continue;
  $dir = $base . $slug; if (is_dir($dir)) {{ $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST); foreach ($it as $x) {{ $x->isDir() ? rmdir($x) : unlink($x); }} }}
  wp_mkdir_p($dir); $z = new ZipArchive(); if ($z->open($f) === true) {{ $z->extractTo($dir); $z->close(); }}
  wp_delete_attachment($mid, true);
}}"""
    r = snippet('TEMP Anchor разархивира скритите лендинги /lp/ (single-use ' + time.strftime('%d.%m') + ')', code, 'single-use')
    print('snippet', r.get('id'), r.get('active'))
    s['extract_snippet'] = r.get('id')
    save(s)
    try:
        urllib.request.urlopen(urllib.request.Request(SITE + '/?anchor_lp_extract=' + str(time.time()), headers={'User-Agent': 'facebookexternalhit/1.1'}), timeout=300).read()
    except Exception as e:
        print('заявката:', e)


ROUTE = r"""add_action('init', function () {
  $p = trim(parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH), '/');
  if (!preg_match('#^(?:nordics-bg/)?lp/([a-z0-9-]+)$#', $p, $m)) return;
  $f = WP_CONTENT_DIR . '/uploads/anchor-lp/' . $m[1] . '/index.html';
  if (!file_exists($f)) return;
  if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
  status_header(200); nocache_headers();
  header('Content-Type: text/html; charset=utf-8');
  header('X-Robots-Tag: noindex, nofollow');
  readfile($f); exit;
}, 0);"""


def route():
    s = state()
    if s.get('route_snippet'):
        print('вече има', s['route_snippet'])
        return
    r = snippet('Скрити адвърториали /lp/<slug>/ само по линк, noindex (Anchor ' + time.strftime('%d.%m.%Y') + ')', ROUTE, 'global')
    print('route', r.get('id'), r.get('active'))
    s['route_snippet'] = r.get('id')
    save(s)


def check():
    for k, (folder, slug) in LPS.items():
        url = f'{SITE}/lp/{slug}/'
        o = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code} %{size_download}', '-A', 'facebookexternalhit/1.1', url], capture_output=True, text=True).stdout
        print(k, url, o)


if __name__ == '__main__':
    os.makedirs(WORK, exist_ok=True)
    {'build': build, 'upload': upload, 'extract': extract, 'route': route, 'check': check}[sys.argv[2]]()
