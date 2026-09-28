# -*- coding: utf-8 -*-
"""Сводит три выгрузки в один файл labels_all.csv.

  side_fix.csv  — папка raw, проход Б (сторона + взгляд)
  counts.csv    — папка raw, проход В (число особей)
  raw2.csv      — папка raw2, проход А (новые клипы, только классы)

Правило для незаполненного count: она пишет, что вне кормушечных клипов число птиц
не больше одной. Значит no_bird -> 0, всё остальное -> 1. Эти значения помечаются
как ВЫВЕДЕННЫЕ, а не размеченные, и считаются отдельно.
"""
import sys as _sys, pathlib as _pl  # общие пути AIS, см. common/aispaths.py
_sys.path.insert(0, str(next(_p / "common" for _p in _pl.Path(__file__).resolve().parents
                            if (_p / "common" / "aispaths.py").is_file())))
import aispaths
aispaths.to_data()  # данные, runs, results и пути в аргументах — от AIS/data
import sys
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import csv, collections

def load(p):
    return {r["file"].strip(): r for r in csv.DictReader(open(p, encoding="utf-8-sig"))}

A, B, C = load("side_fix.csv"), load("counts.csv"), load("raw2.csv")
names = list(A) + [n for n in C if n not in A]
out, inferred = [], 0
for n in names:
    a = A.get(n) or C.get(n)
    b = B.get(n, {})
    lab = (a.get("label") or "").strip()
    cnt = (b.get("count") or "").strip()
    src = "размечено"
    if not cnt.isdigit():
        cnt = "0" if lab == "no_bird" else "1"
        src = "выведено"; inferred += 1
    out.append({"file": n, "label": lab,
                "side": (a.get("side") or "").strip(),
                "fixation": (a.get("fixation") or "").strip(),
                "count": cnt, "count_src": src,
                "note": (a.get("note") or "").strip()})

with open("labels_all.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, ["file","label","side","fixation","count","count_src","note"])
    w.writeheader(); w.writerows(out)

clips = collections.Counter(r["file"].rsplit("_t",1)[0] for r in out)
print(f"кадров всего: {len(out)}, клипов: {len(clips)}")
print(f"count размечен рукой: {len(out)-inferred}, выведен по правилу: {inferred}")
for k in ("side","fixation"):
    c = collections.Counter(r[k] for r in out if r[k])
    print(f"{k}: {dict(c)}  всего {sum(c.values())}")
print("клипы:", dict(sorted(clips.items())))
