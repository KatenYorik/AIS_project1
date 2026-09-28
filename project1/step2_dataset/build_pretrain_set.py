# -*- coding: utf-8 -*-
"""Вырезки из видео WetlandBirds → папки классов для предобучения.

Нужно только если делаешь предобучение. Для поведенческого анализа видео не нужны.

    python build_pretrain_set.py --root D:/wetlandbirds --out datasets/pretrain --per-class 400

Что делает: по аннотациям bounding_boxes.csv вырезает птицу из кадра и кладёт в папку
своего ГРУБОГО класса. Кадры внутри одного видео похожи, поэтому берутся не подряд, а
с прореживанием, и на каждое видео стоит потолок — иначе одно длинное видео займёт
весь класс и модель выучит его фон.
"""
from __future__ import annotations
import sys as _sys, pathlib as _pl  # общие пути AIS, см. common/aispaths.py
_sys.path.insert(0, str(next(_p / "common" for _p in _pl.Path(__file__).resolve().parents
                            if (_p / "common" / "aispaths.py").is_file())))
import aispaths
aispaths.to_data()  # данные, runs, results и пути в аргументах — от AIS/data
import sys
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

import argparse, collections, csv, os, random, sys

# те же грубые классы, что и в нашей схеме
MAP = {
    "feeding":  "feeding",
    "alert":    "alert",
    "preening": "other_behaviour",
    "resting":  "other_behaviour",
    "walking":  "other_behaviour",
    "swimming": "other_behaviour",
    "flying":   "transit",
}


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096); f.seek(0)
        try: dial = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error: dial = csv.excel
        rd = csv.reader(f, dial); rows = list(rd)
    return rows[0], rows[1:]


def load_behaviours(path):
    if not os.path.exists(path): return {}
    _, rows = read_rows(path)
    out = {}
    for r in rows:
        if len(r) < 2: continue
        a, b = r[0].strip(), r[1].strip()
        if a.lstrip("-").isdigit(): out[int(a)] = b
        elif b.lstrip("-").isdigit(): out[int(b)] = a
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="папка с bounding_boxes.csv и videos/")
    ap.add_argument("--out", default="datasets/pretrain")
    ap.add_argument("--per-class", type=int, default=400)
    ap.add_argument("--per-video", type=int, default=25, help="потолок вырезок с одного видео")
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--pad", type=float, default=0.15, help="запас вокруг рамки")
    a = ap.parse_args()

    try:
        import cv2
    except ImportError:
        sys.exit("нужен opencv: pip install opencv-python")

    behav = load_behaviours(os.path.join(a.root, "behaviors_ID.csv"))
    if not behav: sys.exit("не найден behaviors_ID.csv")
    print("классы поведения:", behav)

    header, rows = read_rows(os.path.join(a.root, "bounding_boxes.csv"))
    low = [h.strip().lower() for h in header] if header else []

    def col(*names, default=None):
        for n in names:
            for i, h in enumerate(low):
                if n in h: return i
        return default

    c_vid = col("video", "clip", "file")
    c_fr = col("frame")
    c_b = col("behav", "label")
    c_x1, c_y1, c_x2, c_y2 = col("x1", "xmin", "left"), col("y1", "ymin", "top"), \
                             col("x2", "xmax", "right"), col("y2", "ymax", "bottom")
    if None in (c_vid, c_fr, c_b, c_x1, c_y1, c_x2, c_y2):
        sys.exit(f"не удалось распознать колонки, шапка: {header}")
    print("колонки:", {k: header[v] for k, v in
                       dict(video=c_vid, frame=c_fr, behav=c_b,
                            x1=c_x1, y1=c_y1, x2=c_x2, y2=c_y2).items()})

    # группируем по видео
    by_video = collections.defaultdict(list)
    for r in rows:
        try:
            b = int(float(r[c_b])); fr = int(float(r[c_fr]))
            box = [int(float(r[c])) for c in (c_x1, c_y1, c_x2, c_y2)]
        except (ValueError, IndexError):
            continue
        cls = MAP.get(behav.get(b, "").strip().lower())
        if cls: by_video[r[c_vid]].append((fr, box, cls))

    for c in set(MAP.values()):
        os.makedirs(os.path.join(a.out, c), exist_ok=True)

    rng = random.Random(0)
    saved = collections.Counter()
    videos = sorted(by_video)
    rng.shuffle(videos)

    for vi, vid in enumerate(videos, 1):
        if all(saved[c] >= a.per_class for c in set(MAP.values())): break
        path = None
        for cand in (os.path.join(a.root, "videos", vid),
                     os.path.join(a.root, "videos", vid + ".mp4"),
                     os.path.join(a.root, vid)):
            if os.path.exists(cand): path = cand; break
        if path is None:
            continue
        cap = cv2.VideoCapture(path)
        if not cap.isOpened(): continue

        items = by_video[vid]
        # прореживаем: берём равномерно по времени, не подряд
        rng.shuffle(items)
        took = collections.Counter()
        for fr, box, cls in items:
            if saved[cls] >= a.per_class: continue
            if sum(took.values()) >= a.per_video: break
            if took[cls] >= max(2, a.per_video // 3): continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
            ok, img = cap.read()
            if not ok: continue
            h, w = img.shape[:2]
            x1, y1, x2, y2 = box
            dx, dy = int((x2-x1)*a.pad), int((y2-y1)*a.pad)
            x1, y1 = max(0, x1-dx), max(0, y1-dy)
            x2, y2 = min(w, x2+dx), min(h, y2+dy)
            if x2-x1 < 20 or y2-y1 < 20: continue
            crop = cv2.resize(img[y1:y2, x1:x2], (a.size, a.size))
            name = f"{os.path.splitext(os.path.basename(vid))[0]}_f{fr:06d}.jpg"
            cv2.imwrite(os.path.join(a.out, cls, name), crop,
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
            saved[cls] += 1; took[cls] += 1
        cap.release()
        if vi % 10 == 0:
            print(f"  видео {vi}/{len(videos)}: " +
                  ", ".join(f"{c} {saved[c]}" for c in sorted(saved)))

    print("\nитог:")
    for c in sorted(set(MAP.values())):
        print(f"  {c:16s} {saved[c]:5d}")
    print(f"\nвсего {sum(saved.values())} вырезок в {a.out}")
    print("дальше: обучить на этом, затем дообучить на своей разметке")


if __name__ == "__main__":
    main()
