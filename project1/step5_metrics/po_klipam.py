# -*- coding: utf-8 -*-
"""Разбор качества модели ПО КЛИПАМ, а не одним числом.

    python po_klipam.py --weights runs\\classify\\frozen_ep10\\weights\\best.pt
                        --data datasets\\birds_v1_episode

Одно общее число прячет главное: клипы разные. Здесь модель прогоняется по
проверочным кадрам и результат разбирается по клипам — где она ошибается, на
чём путается и какой клип для неё лёгкий, а какой тяжёлый.

Ничего не обучает и ничего не меняет, только читает готовые веса и кадры.
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

import argparse, collections, os


def f1(cm, labels, i):
    tp = cm[i][i]
    fp = sum(cm[j][i] for j in range(len(labels))) - tp
    fn = sum(cm[i]) - tp
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return 2 * pr * rc / (pr + rc) if pr + rc else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--split", default="val")
    ap.add_argument("--imgsz", type=int, default=224)
    a = ap.parse_args()

    root = os.path.join(a.data, a.split)
    if not os.path.isdir(root):
        sys.exit(f"нет папки {root}")
    classes = sorted(d for d in os.listdir(root)
                     if os.path.isdir(os.path.join(root, d)))

    from ultralytics import YOLO
    model = YOLO(a.weights)

    # кадры с их истинным классом, сгруппированные по клипу
    by_clip = collections.defaultdict(list)
    for c in classes:
        d = os.path.join(root, c)
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                by_clip[f.rsplit("_t", 1)[0]].append((os.path.join(d, f), c))

    total = sum(len(v) for v in by_clip.values())
    print(f"кадров в {a.split}: {total}, клипов: {len(by_clip)}")
    print(f"модель: {a.weights}\n")

    rows, all_true, all_pred = [], [], []
    for clip, items in by_clip.items():
        files = [p for p, _ in items]
        truth = [c for _, c in items]
        pred = []
        for i in range(0, len(files), 64):
            for r in model.predict(files[i:i+64], imgsz=a.imgsz, verbose=False):
                pred.append(r.names[int(r.probs.top1)])
        ok = sum(t == p for t, p in zip(truth, pred))
        rows.append((clip, len(items), ok / len(items),
                     collections.Counter(truth), collections.Counter(pred)))
        all_true += truth; all_pred += pred

    print(f"{'клип':18s} {'кадров':>6s} {'верно':>6s} {'доля':>6s}   истина -> что предсказано")
    for clip, n, acc, tr, pr in sorted(rows, key=lambda r: r[2]):
        miss = ", ".join(f"{c}: {tr[c]}→{pr[c]}" for c in classes if tr[c])
        print(f"{clip:18s} {n:6d} {round(acc*n):6d} {acc:6.3f}   {miss}")

    # общая матрица — чтобы было с чем сверять построчный разбор
    idx = {c: i for i, c in enumerate(classes)}
    cm = [[0]*len(classes) for _ in classes]
    for t, p in zip(all_true, all_pred): cm[idx[t]][idx.get(p, 0)] += 1
    acc = sum(cm[i][i] for i in range(len(classes))) / max(len(all_true), 1)
    macro = sum(f1(cm, classes, i) for i in range(len(classes))) / len(classes)
    print(f"\nвсего: accuracy {acc:.3f}, macro-F1 {macro:.3f}")

    sizes = [sum(r) for r in cm]
    p = max(sizes) / max(sum(sizes), 1)
    print(f"константа на этой выборке: accuracy {p:.3f}, "
          f"macro-F1 {(2*p/(p+1))/len(classes):.3f}")

    print("\nМелкие клипы дают шумную оценку: на двадцати кадрах разница в один")
    print("кадр — это пять процентов. Смотреть надо на порядок величин, а не на")
    print("третий знак, и в первую очередь на клипы, где ошибок заметно больше.")


if __name__ == "__main__":
    main()
