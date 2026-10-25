#!/usr/bin/env python3
"""3:4 -> 4:5 (1080x1350) за Meta + контактни листове по адвърториал за проверка на око.

  python3 finish.py <ugc.json> sheet    -> <ads_dir>/sheet_<П>.jpg (гледай всеки лист: ръце, пръсти, текст, жестове, чаши)
  python3 finish.py <ugc.json> final    -> <ads_dir>/final/<КОД>.jpg
Отхвърлена визия: премести art/<КОД>.png в rejected/, махни ключа ѝ от jobs.tasks.json, оправи сцената, пусни runner-а пак.
"""
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont


def to45(src):
    im = Image.open(src).convert('RGB'); w, h = im.size; nh = int(w * 1.25); top = (h - nh) // 2
    return im.crop((0, top, w, top + nh)).resize((1080, 1350), Image.LANCZOS)


def main(cfg_path, mode):
    cfg = json.load(open(cfg_path)); D = os.path.expanduser(cfg['ads_dir'])
    if mode == 'sheet':
        try:
            f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 24)
        except OSError:
            f = ImageFont.load_default()
        for pre in cfg['lps']:
            fs = sorted(glob.glob(os.path.join(D, 'art', f'{pre}*.png'))); W, H = 360, 450
            sh = Image.new('RGB', (5 * W, 2 * (H + 30)), 'white'); d = ImageDraw.Draw(sh)
            for i, p in enumerate(fs):
                x, y = (i % 5) * W, (i // 5) * (H + 30)
                sh.paste(to45(p).resize((W, H)), (x, y + 30)); d.text((x + 6, y + 2), os.path.basename(p)[:-4], fill='black', font=f)
            sh.save(os.path.join(D, f'sheet_{pre}.jpg'), quality=85)
    else:
        os.makedirs(os.path.join(D, 'final'), exist_ok=True)
        for p in sorted(glob.glob(os.path.join(D, 'art', '*.png'))):
            to45(p).save(os.path.join(D, 'final', os.path.basename(p)[:-4] + '.jpg'), quality=92)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
