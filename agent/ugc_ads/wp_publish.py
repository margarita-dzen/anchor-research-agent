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


# Маршрутът + Meta проследяване (26.10.2026): сървърни PageView/ViewContent през SMPL плъгина, пиксел само със
# съгласие (Complianz), бутоните носят fbclid + utm_* на рекламата. Плейсхолдърите се пълнят от ugc.json "tracking".
ROUTE = r"""/**
 * Anchor hidden LPs /lp/<slug>/ (noindex, only by link) + Meta tracking (26.10.2026).
 *
 * Files: wp-content/uploads/anchor-lp/<slug>/index.html, served raw (no theme).
 * Tracking mirrors the store's "Meta Pixel and cAPI Integration" (SMPL) plugin:
 *  - server PageView + ViewContent through SMPL's own send_server_event (same pixel, token, markets);
 *    fbc comes from ?fbclid, exactly as SMPL does on every store page;
 *  - browser pixel with the same event IDs (dedup), only with Complianz marketing consent;
 *  - buy buttons (?anchor_cart=...) keep fbclid + the ad's utm_* (snippet #29 carries them to the order).
 */
add_action('wp_loaded', function () {
  $p = trim(parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH), '/');
  if (!preg_match('#^(?:nordics-bg/)?lp/([a-z0-9-]+)$#', $p, $m)) return;
  $f = WP_CONTENT_DIR . '/uploads/anchor-lp/' . $m[1] . '/index.html';
  if (!file_exists($f)) return;
  if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
  status_header(200); nocache_headers();
  header('Content-Type: text/html; charset=utf-8');
  header('X-Robots-Tag: noindex, nofollow');

  $html = file_get_contents($f);
  $ev = array();
  $ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
  $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
  $bot = preg_match('/facebookexternalhit|facebot|bot|crawl|spider|preview|headless|lighthouse/i', $ua);
  if (class_exists('SMPL_Meta_CAPI') && $method === 'GET' && !$bot) {
    $vc = array('content_ids' => __CONTENT_IDS__,
      'content_type' => 'product', 'content_name' => __CONTENT_NAME__, 'value' => __VALUE__, 'currency' => 'EUR');
    $ev = array(array('PageView', wp_generate_uuid4(), new stdClass()), array('ViewContent', wp_generate_uuid4(), $vc));
    $send = Closure::bind(function ($n, $id, $d) { $this->send_server_event($n, $id, $d ?: array()); }, SMPL_Meta_CAPI::instance(), 'SMPL_Meta_CAPI');
    foreach ($ev as $e) $send($e[0], $e[1], is_array($e[2]) ? $e[2] : array());
  }
  $js = '<script>(function(){var EV=' . wp_json_encode($ev) . ';'
    . 'function ok(){return /(?:^|;\s*)cmplz_marketing=allow/.test(document.cookie)}'
    . 'if(EV.length&&ok()){!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version="2.0";n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,"script","https://connect.facebook.net/en_US/fbevents.js");'
    . 'fbq("init","__PIXEL__",{country:"bg"});EV.forEach(function(e){fbq("track",e[0],Array.isArray(e[2])?{}:e[2],{eventID:e[1]})})}'
    . 'var q=new URLSearchParams(location.search),keep={};q.forEach(function(v,k){if(/^(utm_[a-z]+|fbclid|gclid)$/.test(k))keep[k]=v});'
    . 'var adUtm=Object.keys(keep).some(function(k){return k.indexOf("utm_")===0});'
    . 'document.addEventListener("click",function(ev){var a=ev.target.closest&&ev.target.closest("a[href*=\"anchor_cart=\"]");if(!a)return;'
    . 'try{var u=new URL(a.href,location.href);if(adUtm)Array.from(u.searchParams.keys()).forEach(function(k){if(k.indexOf("utm_")===0)u.searchParams.delete(k)});'
    . 'Object.keys(keep).forEach(function(k){u.searchParams.set(k,keep[k])});if(!u.searchParams.get("anchor_funnel"))u.searchParams.set("anchor_funnel","lp-' . esc_js($m[1]) . '");a.href=u.toString()}catch(x){}},true);'
    . '})();</script>';
  $i = stripos($html, '</head>');
  $html = $i === false ? $js . $html : substr_replace($html, $js, $i, 0);
  echo $html; exit;
}, 0);"""


def route():
    s = state()
    if s.get('route_snippet'):
        print('вече има', s['route_snippet'])
        return
    tr = CFG.get('tracking', {})
    code = (ROUTE.replace('__PIXEL__', tr.get('pixel', CFG.get('meta', {}).get('pixel', '')))
            .replace('__CONTENT_IDS__', 'array(' + ', '.join("'%s'" % i for i in tr.get('content_ids', [])) + ')')
            .replace('__CONTENT_NAME__', "'%s'" % tr.get('content_name', 'Product')).replace('__VALUE__', str(float(tr.get('value', 0)))))
    r = snippet('Скрити адвърториали /lp/<slug>/ само по линк, noindex + Meta (Anchor ' + time.strftime('%d.%m.%Y') + ')', code, 'global')
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
