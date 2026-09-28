# -*- coding: utf-8 -*-
"""Две версии датасета в ClearML: начальная и улучшенная — требование задания.

    python clearml_versions.py

Что делает и почему именно так.

Задание требует «at least an initial version and an improved version (after extra
collection or re-annotation)». У нас для этого есть готовое честное основание:

    raw/    706 кадров, 9 клипов   — первая съёмочная сессия
    raw2/   240 кадров, 7 клипов   — вторая съёмка, другой день и свет

Поэтому v1 собирается только из raw, а v2 — из raw и raw2. Вторая версия
регистрируется как ПОТОМОК первой (parent_datasets), и тогда ClearML хранит не
вторую копию, а разницу, и показывает происхождение — то самое, ради чего в
лекции 5 датасеты держат не в git.

Раскладка по классам берётся из labels_all.csv, свёртка та же, что в обучении.
Папки собираются в datasets/clearml/ и после заливки не нужны.
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

import argparse, collections, csv, os, shutil

ROOT = str(aispaths.DATA)
COURSE3 = {"head_down": "feeding", "handling": "feeding",
           "head_up_ahead": "alert", "head_up_turnL": "alert",
           "head_up_turnR": "alert", "no_bird": "empty"}
CLASSES = ["feeding", "alert", "empty"]


def collect(labels, folders):
    """Скопировать кадры указанных папок по классам. Возвращает путь и счётчик."""
    where = {}
    for folder in folders:
        d = os.path.join(ROOT, folder)
        if not os.path.isdir(d):
            print(f"  нет папки {folder} — пропускаю"); continue
        for f in os.listdir(d):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                where[os.path.splitext(f)[0]] = os.path.join(d, f)

    out = os.path.join(ROOT, "datasets", "clearml",
                       "birds_v1" if len(folders) == 1 else "birds_v2")
    if os.path.exists(out): shutil.rmtree(out)
    cnt = collections.Counter()
    for r in csv.DictReader(open(os.path.join(ROOT, labels), encoding="utf-8-sig")):
        cls = COURSE3.get(r["label"].strip())
        src = where.get(r["file"].strip())
        if not cls or not src: continue
        d = os.path.join(out, cls); os.makedirs(d, exist_ok=True)
        shutil.copy2(src, os.path.join(d, os.path.basename(src)))
        cnt[cls] += 1
    clips = {os.path.splitext(os.path.basename(p))[0].rsplit("_t", 1)[0]
             for p in where.values()}
    return out, cnt, len(clips)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="labels_all.csv")
    ap.add_argument("--project", default="AIS-birds")
    ap.add_argument("--dry-run", action="store_true", help="только собрать папки, не заливать")
    a = ap.parse_args()

    print("=" * 68)
    print("ВЕРСИЯ 1: только первая съёмка (raw)")
    print("=" * 68)
    p1, c1, n1 = collect(a.labels, ["raw"])
    print(f"  {sum(c1.values())} кадров, {n1} клипов: " +
          "  ".join(f"{c} {c1[c]}" for c in CLASSES))

    print("\n" + "=" * 68)
    print("ВЕРСИЯ 2: обе съёмки (raw + raw2)")
    print("=" * 68)
    p2, c2, n2 = collect(a.labels, ["raw", "raw2"])
    print(f"  {sum(c2.values())} кадров, {n2} клипов: " +
          "  ".join(f"{c} {c2[c]}" for c in CLASSES))
    print(f"\n  прирост: +{sum(c2.values()) - sum(c1.values())} кадров, "
          f"+{n2 - n1} клипов")

    if a.dry_run:
        print("\n--dry-run: папки собраны, заливки не было")
        return

    from clearml import Dataset
    print("\nзаливаю v1 …")
    d1 = Dataset.create(dataset_project=a.project, dataset_name="birds",
                        dataset_version="1.0.0",
                        description="Первая съёмочная сессия: 9 клипов, 706 кадров")
    d1.add_files(p1); d1.upload(); d1.finalize()
    print(f"  v1 id: {d1.id}")

    print("\nзаливаю v2 как потомка v1 …")
    d2 = Dataset.create(dataset_project=a.project, dataset_name="birds",
                        dataset_version="2.0.0", parent_datasets=[d1.id],
                        description="Плюс вторая съёмка: 16 клипов, 946 кадров, "
                                    "другой день и освещение")
    d2.add_files(p2); d2.upload(); d2.finalize()
    print(f"  v2 id: {d2.id}")

    print("\nГотово. В отчёт идут оба id и ссылка на проект в ClearML.")
    print("Папки datasets/clearml/ после этого можно удалить — данные уже в ClearML.")


if __name__ == "__main__":
    main()
