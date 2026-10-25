#!/usr/bin/env python3
"""UGC ло-фи визии без продукт и без текст: сцени -> jobs.json за runner.mjs (Nordics 25.10.2026, одобрено от Валентин).

Сцените се пишат на ръка в <run>/ugc/scenes.json: {"E01": "сцена…", …}, по 10 на адвърториал,
всички уникални (feedback_no_repeated_scenes_in_batch). Префиксът е буквата на адвърториала от ugc.json.

  python3 prompts.py <run>/ugc/ugc.json          -> <out>/jobs.json
  node runner.mjs <out>/jobs.json                -> <out>/art/<КОД>.png (gpt-image-2 text-to-image, 3:4, 2K)
"""
import json, os, sys

# Стилът, който мина: снимка от телефона на родител, не студио. Езикът на средата се сменя от ugc.json ("locale").
BASE = ("Authentic amateur smartphone photo, looks like a real {locale} parent's phone snap posted on Facebook or sent in a family Viber group, "
        "imperfect casual framing, mild grain and softness, natural uneven light, slightly dull true-to-life colours, real unretouched skin, "
        "ordinary lived-in {locale} apartment or town setting, normal everyday people, no model looks, no styling, not a studio photo. Vertical. ")
# Твърдите забрани: деца облечени, без продукта (TOF без продукт), без герои, без текст върху снимката.
END = (" All children are fully dressed in ordinary clothes or full-length pyjamas. "
       "No {product} anywhere in the image, no brand packaging. "
       "No cartoon characters, no licensed characters, no superhero or film characters on clothes, toys or walls. "
       "No text, no letters, no numbers, no logos, no watermark, no captions, no UI anywhere in the image. "
       "Avoid: AI-looking glossy skin, perfect symmetry, extra fingers, stock-photo smiles, medical gore.")


def main(cfg_path):
    cfg = json.load(open(cfg_path))
    run = os.path.dirname(os.path.abspath(cfg_path))
    out = os.path.expanduser(cfg['ads_dir'])
    scenes = json.load(open(os.path.join(run, 'scenes.json')))
    assert len(set(scenes.values())) == len(scenes), 'повторени сцени'
    for pre in cfg['lps']:
        n = sum(1 for k in scenes if k.startswith(pre))
        assert n == cfg.get('per_lp', 10), (pre, n)
    b = BASE.format(locale=cfg.get('locale', 'Bulgarian'))
    e = END.format(product=cfg.get('product_negative', 'electric toothbrush'))
    jobs = [dict(prompt=b + s + e, filesUrl=[], ratio='3:4', outPath=os.path.join(out, 'art', f'{c}.png')) for c, s in scenes.items()]
    os.makedirs(os.path.join(out, 'art'), exist_ok=True)
    json.dump(jobs, open(os.path.join(out, 'jobs.json'), 'w'), ensure_ascii=False, indent=1)
    print(len(jobs), 'задачи ->', os.path.join(out, 'jobs.json'))


if __name__ == '__main__':
    main(sys.argv[1])
