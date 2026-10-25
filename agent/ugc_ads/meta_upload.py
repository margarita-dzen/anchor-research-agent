#!/usr/bin/env python3
"""UGC рекламите в Meta: 1 CBO кампания, по 1 ад сет на адвърториал, неговите 10 реклами вътре (Nordics 25.10.2026).
Кампанията се създава PAUSED, ад сетовете и рекламите ACTIVE: тръгват с един ключ, когато Валентин каже.
Имената са само на латиница (feedback_no_cyrillic_in_ad_accounts). Идемпотентно по име, пази <ads_dir>/uploaded_meta.json.

  python3 meta_upload.py <ugc.json> [--dry]
Токенът е във файла meta.token_file (извън репото). Копито: <ads_dir>/copy/<П>.md във формата от docs/ugc-ads.md.
"""
import json, os, re, sys, time, requests

CFG = json.load(open(sys.argv[1]))
M = CFG['meta']
D = os.path.expanduser(CFG['ads_dir'])
TOKEN = open(os.path.expanduser(M['token_file'])).read().strip()
G = 'https://graph.facebook.com/v21.0'
ACT = M['act']
DRY = '--dry' in sys.argv


def api(method, path, **data):
    data['access_token'] = TOKEN
    for attempt in range(5):
        j = requests.request(method, f'{G}/{path}', data=data, timeout=120).json()
        if 'error' in j:
            e = j['error']
            # subcode 99 "unknown error" и is_transient минават при повторение (25.10.2026)
            if (e.get('is_transient') or e.get('error_subcode') == 99) and attempt < 4:
                time.sleep(5); continue
            raise RuntimeError(json.dumps(e, ensure_ascii=False)[:400])
        return j


def find(edge, name, parent=ACT):
    for x in requests.get(f'{G}/{parent}/{edge}', params={'fields': 'id,name', 'limit': 200, 'access_token': TOKEN}, timeout=90).json().get('data', []):
        if x['name'] == name:
            return x['id']


def upload_image(path):
    tmp = '/tmp/ugc_' + os.path.basename(path)  # adimages не понася кирилица и интервали в пътя
    open(tmp, 'wb').write(open(path, 'rb').read())
    j = requests.post(f'{G}/{ACT}/adimages', files={'source': (os.path.basename(tmp), open(tmp, 'rb'), 'image/jpeg')},
                      data={'access_token': TOKEN}, timeout=180).json()
    if 'error' in j:
        raise RuntimeError(json.dumps(j['error'], ensure_ascii=False)[:300])
    return list(j['images'].values())[0]['hash']


def parse(pre):
    md = open(os.path.join(D, 'copy', f'{pre}.md'), encoding='utf-8').read()
    ads = []
    for b in re.split(r'\n(?=## [A-Z]\d\d )', md)[1:]:
        body = b.split('**CTA:**', 1)[1].split('\n', 1)[1]
        body = re.split(r'\n---\s*(\n|$)', body)[0].strip()
        url = re.search(re.escape(CFG['site']['base']) + r'/lp/[a-z0-9-]+/\?(\S+)', body)
        assert url, (b[3:6], 'няма линк с UTM в текста')
        ads.append(dict(code=b[3:6], hl=re.search(r'\*\*Хедлайн:\*\* *(.+)', b).group(1).strip(),
                        ds=re.search(r'\*\*Описание:\*\* *(.+)', b).group(1).strip(), body=body, tags=url.group(1)))
    assert len(ads) == CFG.get('per_lp', 10), (pre, len(ads))
    return ads


def adset_payload(name, cid):
    return dict(name=name, campaign_id=cid, status='ACTIVE', billing_event='IMPRESSIONS', optimization_goal='OFFSITE_CONVERSIONS',
                promoted_object=json.dumps({'pixel_id': M['pixel'], 'custom_event_type': 'PURCHASE'}),
                attribution_spec=json.dumps([{'event_type': 'CLICK_THROUGH', 'window_days': 7}, {'event_type': 'VIEW_THROUGH', 'window_days': 1}]),
                targeting=json.dumps(M.get('targeting') or {'age_min': 18, 'age_max': 65,
                                     'geo_locations': {'countries': [M.get('country', 'BG')], 'location_types': ['home', 'recent']},
                                     'targeting_automation': {'advantage_audience': 1}}))


plan = {pre: parse(pre) for pre in CFG['lps']}
if DRY:
    print(M['campaign'], '| CBO', M['budget_cents'] / 100, '/ден')
    for pre, ads in plan.items():
        print(pre, CFG['lps'][pre]['adset'], [(a['code'], len(a['body'])) for a in ads])
    sys.exit()

cid = find('campaigns', M['campaign']) or api('POST', f'{ACT}/campaigns', name=M['campaign'], objective='OUTCOME_SALES', status='PAUSED',
                                               buying_type='AUCTION', daily_budget=M['budget_cents'], bid_strategy='LOWEST_COST_WITHOUT_CAP',
                                               special_ad_categories=json.dumps([]))['id']
outp = os.path.join(D, 'uploaded_meta.json')
out = json.load(open(outp)) if os.path.exists(outp) else {'campaign_id': cid, 'adsets': {}, 'ads': {}}
for pre, lp in CFG['lps'].items():
    link = f"{CFG['site']['base']}/lp/{lp['slug']}/"
    aname = f"{M['prefix']} | {lp['adset']} | Broad {M.get('country', 'BG')}"
    aid = find('adsets', aname, parent=cid) or api('POST', f'{ACT}/adsets', **adset_payload(aname, cid))['id']
    out['adsets'][pre] = aid
    existing = {x['name'] for x in requests.get(f'{G}/{aid}/ads', params={'fields': 'name', 'limit': 200, 'access_token': TOKEN}, timeout=90).json().get('data', [])}
    for a in plan[pre]:
        ad_name = f"{M['prefix']} | {a['code']} | UGC lofi DR"
        if ad_name in existing:
            continue
        h = upload_image(os.path.join(D, 'final', f"{a['code']}.jpg"))
        cr = api('POST', f'{ACT}/adcreatives', name=f"{M['prefix']} {a['code']} UGC lofi",
                 object_story_spec=json.dumps({'page_id': M['page'], 'instagram_user_id': M['ig'],
                     'link_data': {'image_hash': h, 'link': link, 'message': a['body'], 'name': a['hl'], 'description': a['ds'],
                                   'call_to_action': {'type': M.get('cta', 'SHOP_NOW'), 'value': {'link': link}}}}, ensure_ascii=False),
                 url_tags=a['tags'])['id']
        ad = api('POST', f'{ACT}/ads', name=ad_name, adset_id=aid, creative=json.dumps({'creative_id': cr}),
                 status='ACTIVE', conversion_domain=M['domain'])['id']
        out['ads'][a['code']] = {'ad_id': ad, 'creative_id': cr, 'adset_id': aid, 'image_hash': h}
        json.dump(out, open(outp, 'w'), ensure_ascii=False, indent=1)
        print(a['code'], ad); time.sleep(0.4)
print('кампания', cid, '| реклами', len(out['ads']), '| сверка: GET /<adset>/ads?fields=creative{object_story_spec,url_tags}')
