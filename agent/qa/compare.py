"""Оригинал срещу клонинг: подравняване на секциите, разлики, оценка 0-100 и снимки едно до друго.

    python3 agent/qa/compare.py <оригинал: URL или папка src/> <клонинг: URL> --out qa_out/x [--threshold 85]

Какво сравнява (за всяка ширина, по подразбиране 390 и 1440):
  - броя секции; липсващи, излишни и разместени секции;
  - съотношение на височините по двойки;
  - броя елементи: снимки/видеа, точки в списък, повтарящи се карти (причини, отзиви), бутони;
  - номерираните точки в заглавията (10 причини срещу 8).
Подравняването е глобално (Needleman-Wunsch) по тип на секцията, медии, относителна позиция и височина, номер в заглавието.
Текстът на заглавията почти не тежи, защото оригиналът е на друг език.

Изход в --out: compare.json, compare.txt (кратък доклад на български), cmp_<w>_<nn>.jpg (оригинал | клонинг),
original/ и clone/ (снимките и outline_<w>.json от capture.py).
Оценка = средно от ширините; „готово“ при >= --threshold (85 по подразбиране).
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FONT_PATHS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
TYPE_GROUPS = [{"gallery", "image"}, {"list", "reviews"}, {"cta", "offer"}, {"text", "image"}, {"list", "text"},
               {"list", "image"}, {"gallery", "reviews"}, {"video", "image"}, {"video", "gallery"}]
DISTINCT_TYPES = {"offer", "reviews", "faq", "video", "gallery"}
MATCH_MIN = 0.5      # двойка под това е „различна секция на същото място“
MATCH_OFFSET = 0.4   # двойка се предпочита пред две празнини при сходство > 0,3
GAP = -0.05


# ---------- чиста логика ----------

def media(s):
    return s.get("img", 0) + s.get("bgimg", 0) + s.get("video", 0)


def items(s):
    return max(s.get("li", 0), s.get("repeat", 0))


def closeness(a, b):
    if a == b:
        return 1.0
    return 1.0 - abs(a - b) / float(max(a, b, 1))


def type_sim(a, b):
    if a == b:
        return 1.0
    for g in TYPE_GROUPS:
        if a in g and b in g:
            return 0.5
    return 0.0


def heading_shape(a, b):
    """Формата на заглавието без значение от езика: има ли, завършва ли на : ? !, сходна дължина."""
    ta, tb = (a.get("heading") or "").strip(), (b.get("heading") or "").strip()
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    end = 1.0 if (ta[-1] in ":?!") == (tb[-1] in ":?!") and (ta[-1] if ta[-1] in ":?!" else "") == (tb[-1] if tb[-1] in ":?!" else "") else 0.0
    return 0.5 * end + 0.5 * closeness(len(ta), len(tb))


def section_sim(a, b, Ha, Hb):
    """Сходство 0..1 между секция a (оригинал) и b (клонинг)."""
    pa = (a["y"] + a["h"] / 2.0) / max(Ha, 1)
    pb = (b["y"] + b["h"] / 2.0) / max(Hb, 1)
    pos = max(0.0, 1.0 - abs(pa - pb) * 3)
    ha, hb = a["h"] / float(max(Ha, 1)), b["h"] / float(max(Hb, 1))
    hgt = min(ha, hb) / max(ha, hb, 1e-6)
    sim = (0.25 * type_sim(a.get("type"), b.get("type")) + 0.15 * closeness(media(a), media(b))
           + 0.1 * closeness(items(a), items(b)) + 0.3 * pos + 0.1 * hgt + 0.1 * heading_shape(a, b))
    na, nb = a.get("num"), b.get("num")
    if na and nb:
        sim = 0.75 * sim + 0.25 * (1.0 if na == nb else 0.0)
    elif na or nb:
        sim = 0.9 * sim
    return round(sim, 3)


def align(A, B, Ha, Hb, sim=section_sim):
    """Глобално подравняване. Връща списък (i|None, j|None, сходство)."""
    n, m = len(A), len(B)
    S = [[sim(A[i], B[j], Ha, Hb) for j in range(m)] for i in range(n)]
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0] = D[i - 1][0] + GAP
    for j in range(1, m + 1):
        D[0][j] = D[0][j - 1] + GAP
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = max(D[i - 1][j - 1] + S[i - 1][j - 1] - MATCH_OFFSET, D[i - 1][j] + GAP, D[i][j - 1] + GAP)
    out, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(D[i][j] - (D[i - 1][j - 1] + S[i - 1][j - 1] - MATCH_OFFSET)) < 1e-9:
            out.append((i - 1, j - 1, S[i - 1][j - 1])); i -= 1; j -= 1
        elif i > 0 and abs(D[i][j] - (D[i - 1][j] + GAP)) < 1e-9:
            out.append((i - 1, None, 0.0)); i -= 1
        else:
            out.append((None, j - 1, 0.0)); j -= 1
    out.reverse()
    return out, S


def max_number(secs):
    nums = [s.get("num") for s in secs if s.get("num")]
    return max(nums) if nums else 0


def count_mismatch(a, b):
    """Разлики в броячите на двойка секции, които си струва да се кажат."""
    out = []
    for key, label in (("media", "снимки/видеа"), ("li", "точки в списък"), ("repeat", "повтарящи се карти"),
                       ("button", "бутони")):
        va = media(a) if key == "media" else a.get(key, 0)
        vb = media(b) if key == "media" else b.get(key, 0)
        if va != vb and abs(va - vb) >= max(1, round(0.2 * max(va, vb))):
            out.append((label, va, vb))
    return out


def analyze(A, B, Ha, Hb):
    """Пълен анализ на една ширина: подравняване, разлики, оценка."""
    path, S = align(A, B, Ha, Hb)
    pairs, missing, extra = [], [], []
    for i, j, s in path:
        if i is not None and j is not None:
            pairs.append((i, j, s))
        elif i is not None:
            missing.append(i)
        else:
            extra.append(j)
    # разместени: липсваща секция, която прилича силно на излишна
    moved = []
    for i in list(missing):
        best = max(((S[i][j], j) for j in extra), default=(0, None))
        if best[1] is not None and best[0] >= 0.75 and A[i].get("type") == B[best[1]].get("type") and A[i].get("type") in DISTINCT_TYPES:
            moved.append((i, best[1], best[0]))
            missing.remove(i); extra.remove(best[1])
    good = [p for p in pairs if p[2] >= MATCH_MIN]
    weak = [p for p in pairs if p[2] < MATCH_MIN]
    diffs = []
    height = []
    count_ok = 0
    for i, j, s in pairs:
        r = B[j]["h"] / float(max(A[i]["h"], 1))
        height.append(r)
        mm = count_mismatch(A[i], B[j])
        if not mm:
            count_ok += 1
        if mm or r < 0.5 or r > 2.0 or s < MATCH_MIN:
            diffs.append(dict(orig=i + 1, clone=j + 1, sim=s, height_ratio=round(r, 2), counts=mm,
                              orig_type=A[i].get("type"), clone_type=B[j].get("type")))
    n = max(len(A), len(B), 1)
    structure = len(good) / float(n)
    mean_sim = sum(p[2] for p in pairs) / float(len(pairs)) if pairs else 0.0
    h_score = sum(min(r, 1 / r) if r > 0 else 0 for r in height) / float(len(height)) if height else 0.0
    page_r = Hb / float(max(Ha, 1))
    h_score = 0.8 * h_score + 0.2 * min(page_r, 1 / page_r if page_r else 0)
    c_score = count_ok / float(len(pairs)) if pairs else 0.0
    score = round(40 * structure + 20 * mean_sim + 20 * h_score + 20 * c_score, 1)
    return dict(score=score, sections_orig=len(A), sections_clone=len(B), height_orig=Ha, height_clone=Hb,
                parts=dict(structure=round(structure, 3), similarity=round(mean_sim, 3), heights=round(h_score, 3),
                           counts=round(c_score, 3)),
                path=[[i, j, s] for i, j, s in path], missing=missing, extra=extra, moved=moved,
                weak=[[i, j, s] for i, j, s in weak], diffs=diffs,
                numbered=dict(orig=max_number(A), clone=max_number(B)),
                totals=dict(orig={k: sum((media(s) if k == "media" else s.get(k, 0)) for s in A) for k in ("media", "video", "li", "button")},
                            clone={k: sum((media(s) if k == "media" else s.get(k, 0)) for s in B) for k in ("media", "video", "li", "button")}))


def short(s, n=60):
    t = (s.get("heading") or s.get("text") or "").replace("\n", " ")
    return t[:n] + ("…" if len(t) > n else "")


def text_report(res, threshold):
    """Кратък доклад на български."""
    L = []
    verdict = "ГОТОВО" if res["score"] >= threshold else "НЕ Е ГОТОВО"
    L.append(f"Оценка за сходство: {res['score']}/100 (праг {threshold}) → {verdict}")
    for w, r in res["widths"].items():
        A, B = r["_A"], r["_B"]
        L.append("")
        L.append(f"[{w} px] оценка {r['score']} | секции: оригинал {r['sections_orig']}, клонинг {r['sections_clone']} | "
                 f"височина {r['height_orig']} → {r['height_clone']} px ({r['height_clone'] / max(r['height_orig'], 1):.2f}x)")
        for note in r.get("notes", []):
            L.append(f"  ! {note}")
        if r["numbered"]["orig"] or r["numbered"]["clone"]:
            if r["numbered"]["orig"] != r["numbered"]["clone"]:
                L.append(f"  ! номерирани точки: оригинал {r['numbered']['orig']}, клонинг {r['numbered']['clone']}")
        to, tc = r["totals"]["orig"], r["totals"]["clone"]
        L.append(f"  общо снимки/видеа {to['media']} → {tc['media']}, видеа {to['video']} → {tc['video']}, "
                 f"точки {to['li']} → {tc['li']}, бутони {to['button']} → {tc['button']}")
        for i in r["missing"]:
            L.append(f"  - ЛИПСВА секция {i + 1} ({A[i]['type']}, {A[i]['h']} px): {short(A[i])}")
        for j in r["extra"]:
            L.append(f"  + ИЗЛИШНА секция {j + 1} в клонинга ({B[j]['type']}, {B[j]['h']} px): {short(B[j])}")
        for i, j, s in r["moved"]:
            L.append(f"  ~ РАЗМЕСТЕНА: оригинал {i + 1} „{short(A[i], 40)}“ е на място {j + 1} в клонинга")
        for d in r["diffs"]:
            i, j = d["orig"] - 1, d["clone"] - 1
            bits = []
            if d["sim"] < MATCH_MIN:
                bits.append(f"различна секция ({d['orig_type']} → {d['clone_type']}, сходство {d['sim']})")
            if d["height_ratio"] < 0.5 or d["height_ratio"] > 2.0:
                bits.append(f"височина x{d['height_ratio']}")
            for label, va, vb in d["counts"]:
                bits.append(f"{label} {va} → {vb}")
            L.append(f"  * {d['orig']}↔{d['clone']} „{short(A[i], 40)}“: " + "; ".join(bits))
    return "\n".join(L)


# ---------- снимки едно до друго ----------

def _font(size):
    from PIL import ImageFont
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def crop_section(img, s, scale, max_h):
    if img is None or s is None:
        return None
    top, bot = int(s["y"] * scale), int((s["y"] + s["h"]) * scale)
    if top >= img.height:
        return None
    c = img.crop((0, top, img.width, min(bot, img.height, top + int(max_h * scale))))
    return c


def side_by_side(imgA, imgB, a, b, scaleA, scaleB, col_w, label, max_h=2400):
    from PIL import Image, ImageDraw
    cols = []
    for img, s, sc in ((imgA, a, scaleA), (imgB, b, scaleB)):
        c = crop_section(img, s, sc, max_h)
        if c is not None:
            c = c.resize((col_w, max(1, int(c.height * col_w / c.width))))
        cols.append(c)
    h = max([c.height for c in cols if c is not None] + [200])
    head = 54
    out = Image.new("RGB", (col_w * 2 + 30, h + head), (235, 235, 235))
    d = ImageDraw.Draw(out)
    f = _font(15)
    for k, (c, s, name) in enumerate(zip(cols, (a, b), ("ОРИГИНАЛ", "КЛОНИНГ"))):
        x = k * (col_w + 30)
        cap = f"{name}" + (f" | {s['type']} | {s['h']} px" if s else " | НЯМА")
        d.text((x + 6, 6), cap, fill=(20, 20, 20), font=f)
        d.text((x + 6, 28), (short(s, 48) if s else ""), fill=(90, 90, 90), font=f)
        if c is not None:
            out.paste(c, (x, head))
        else:
            d.rectangle([x, head, x + col_w, head + 200], fill=(255, 220, 220) if s is None else (240, 240, 200))
            d.text((x + 10, head + 90), "липсва" if s is None else "извън снимката", fill=(160, 0, 0), font=_font(22))
    d.text((col_w + 4, head + 4), label, fill=(120, 0, 0), font=_font(12))
    return out


def write_pairs(r, oA, oB, out_dir, w):
    files = []
    col_w = 390 if w < 700 else 720
    for k, (i, j, s) in enumerate(r["path"]):
        a = oA["sections"][i] if i is not None else None
        b = oB["sections"][j] if j is not None else None
        label = f"{s:.2f}" if (a and b) else ""
        im = side_by_side(oA.get("_img"), oB.get("_img"), a, b, oA.get("scale", 1.0), oB.get("scale", 1.0), col_w, label)
        p = os.path.join(out_dir, f"cmp_{w}_{k + 1:02d}.jpg")
        im.save(p, quality=78)
        files.append(p)
    return files


def compare(original, clone, out_dir, widths=(390, 1440), threshold=85, max_height=None, images=True):
    from capture import capture, DEFAULT_MAX_HEIGHT
    mh = max_height or DEFAULT_MAX_HEIGHT
    os.makedirs(out_dir, exist_ok=True)
    oa = capture(original, os.path.join(out_dir, "original"), widths=widths, max_height=mh)
    ob = capture(clone, os.path.join(out_dir, "clone"), widths=widths, max_height=mh)
    res = dict(original=original, clone=clone, threshold=threshold, widths={})
    for w in widths:
        A, B = oa[w]["sections"], ob[w]["sections"]
        r = analyze(A, B, oa[w]["H"], ob[w]["H"])
        r["notes"] = [f"оригинал: {n}" for n in oa[w].get("notes", [])] + [f"клонинг: {n}" for n in ob[w].get("notes", [])]
        if images:
            r["images"] = write_pairs(r, oa[w], ob[w], out_dir, w)
        r["_A"], r["_B"] = A, B
        res["widths"][w] = r
    res["score"] = round(sum(r["score"] for r in res["widths"].values()) / len(res["widths"]), 1)
    res["ready"] = res["score"] >= threshold
    txt = text_report(res, threshold)
    res["report"] = txt
    dump = {k: v for k, v in res.items() if k != "widths"}
    dump["widths"] = {}
    for w, r in res["widths"].items():
        rr = {k: v for k, v in r.items() if not k.startswith("_")}
        rr["sections_original"] = r["_A"]
        rr["sections_clone"] = r["_B"]
        dump["widths"][w] = rr
    json.dump(dump, open(os.path.join(out_dir, "compare.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(out_dir, "compare.txt"), "w").write(txt + "\n")
    return res


def main():
    ap = argparse.ArgumentParser(description="Оригинал срещу клонинг по секции (headless).")
    ap.add_argument("original", help="URL на оригинала или папка src/ със запазен оригинал")
    ap.add_argument("clone", help="URL на клонинга (може и с ?preview_theme_id=)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--widths", default="390,1440")
    ap.add_argument("--threshold", type=float, default=85)
    ap.add_argument("--max-height", type=int, default=None, help="таван на снимката в px (16000 по подразбиране)")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    res = compare(a.original, a.clone, a.out, widths=[int(x) for x in a.widths.split(",")], threshold=a.threshold,
                  max_height=a.max_height, images=not a.no_images)
    print(res["report"])
    sys.exit(0 if res["ready"] else 1)


if __name__ == "__main__":
    main()
