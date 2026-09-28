# -*- coding: utf-8 -*-
"""Интервальная разметка → покадровые метки на любой частоте.

    python expand_intervals.py intervals_snegir2692.csv --fps 4

Интервальная разметка (когда началось и когда кончилось поведение) не зависит от
частоты кадров: она описывает само поведение, а не картинки. Поэтому из неё можно
получить метки для 2, 4 или 25 кадров в секунду — сколько понадобится анализу.

Выход: labels_<clip>_<fps>fps.csv со столбцами file,label — тот же формат, что
понимает apply_labels.py.
"""
import sys as _sys, pathlib as _pl  # общие пути AIS, см. common/aispaths.py
_sys.path.insert(0, str(next(_p / "common" for _p in _pl.Path(__file__).resolve().parents
                            if (_p / "common" / "aispaths.py").is_file())))
import aispaths
aispaths.to_data()  # данные, runs, results и пути в аргументах — от AIS/data
import sys
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import argparse, collections, csv, os

ap = argparse.ArgumentParser()
ap.add_argument("csv_path")
ap.add_argument("--fps", type=float, default=4.0)
ap.add_argument("--out", default=None)
a = ap.parse_args()

rows = []
with open(a.csv_path, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append((r["clip"], float(r["start_s"]), float(r["end_s"]), r["label"]))

# проверка целостности: интервалы должны идти подряд, без дыр и без наложений
rows.sort(key=lambda r: r[1])
for (c1, s1, e1, _), (c2, s2, e2, _) in zip(rows, rows[1:]):
    if abs(e1 - s2) > 1e-9:
        raise SystemExit(f"разрыв или наложение между {e1} и {s2}")

clip = rows[0][0]
end = rows[-1][2]
step = 1.0 / a.fps
out = a.out or f"labels_{clip}_{int(a.fps)}fps.csv"

cnt = collections.Counter()
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["file", "label", "t_sec"])
    i = 0
    while True:
        t = i * step
        if t >= end:
            break
        lab = next((l for _, s, e, l in rows if s <= t < e), None)
        if lab:
            # имя кадра: время в десятых долях секунды, как в raw/
            w.writerow([f"{clip}_t{int(round(t*10)):05d}", lab, f"{t:.2f}"])
            cnt[lab] += 1
        i += 1

total = sum(cnt.values())
print(f"{out}: {total} меток при {a.fps} к/с")
for k, v in cnt.most_common():
    print(f"  {k:11s} {v:5d}  ({v/total*100:.1f}%)")

# сводка по сериям
runs = [(l, e - s) for _, s, e, l in rows]
work = [d for l, d in runs if l in ("head_down", "head_up")]
print(f"\nинтервалов всего: {len(rows)}, из них рабочих: {len(work)}")
print(f"средняя длина рабочего интервала: {sum(work)/len(work):.1f} с")
