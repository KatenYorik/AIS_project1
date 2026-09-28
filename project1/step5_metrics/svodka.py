# -*- coding: utf-8 -*-
"""Сводка по всем запускам: читает results/*.json и строит таблицу для отчёта.

    python svodka.py

Ничего не считает заново и ничего не портит — только читает готовые json.
Окно с обучением можно спокойно закрывать: все числа лежат на диске.
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

import glob, json, os

ROOT = str(aispaths.DATA)
CLS = ["feeding", "alert", "empty"]

# как называется запуск -> что он проверяет
SMYSL = {
    "small_33":        "треть обучающей выборки",
    "small_100":       "вся выборка (точка отсчёта)",
    "aug_off":         "без аугментации",
    "aug_strong":      "сильная аугментация",
    "frozen":          "замороженный backbone",
    "small_100_random": "СЛУЧАЙНОЕ деление по кадрам (нечестное)",
    "base":            "шесть мелких классов",
    "frozen_augoff":   "заморозка + без аугментации (лучший на своей съёмке)",
    "frozen_ep10":     "деление по ЭПИЗОДАМ 10 c",
    "frozen_ep10_noryab": "эпизоды 10 c, без дрозда",
    "frozen_drop":     "клипы, дрозд убран из обучения",
    "frozen_fixval":   "в проверке снегирь + дрозд + кормушка",
    # ВНИМАНИЕ: у этих двух строк ДРУГАЯ задача и другая константа.
    # stage1 — 13 видов WetlandBirds, сравнивать можно только по «к константе».
    "pretrain_stage1": "13 видов WetlandBirds — ДРУГАЯ задача, своя константа 0.105",
    "pretrain_stage2": "предобучение + своя съёмка — ИТОГОВАЯ МОДЕЛЬ",
}

# пары «что с чем сравнивать» — это и есть эксперименты чек-листа
PARY = [
    ("small_33", "small_100", "объём данных: треть против всей"),
    ("aug_off", "aug_strong", "аугментация: выкл против сильной"),
    ("small_100", "frozen", "заморозка: полное дообучение против замороженного"),
    ("small_100", "small_100_random", "ДЕЛЕНИЕ: по клипам против случайного"),
    ("frozen_augoff", "frozen_ep10", "ЕДИНИЦА ДЕЛЕНИЯ: клип против эпизода"),
    ("frozen_augoff", "frozen_drop", "исключение дрозда из обучения, та же валидация"),
    ("frozen_augoff", "pretrain_stage2", "ПРЕДОБУЧЕНИЕ: только своя съёмка против WetlandBirds + своя"),
]


def planka(d):
    """Сильнейшая константа НА ЭТОЙ валидации: доля самого частого истинного класса.

    Считается из матрицы ошибок, а не берётся из json: ранние запуски были сделаны
    до того, как это число стало записываться, и сравнивать их надо по той же мерке.
    """
    cm = d.get("confusion", [])
    if not cm: return d.get("baseline_accuracy", 0.0)
    sums = [sum(r) for r in cm]
    return max(sums) / max(sum(sums), 1)


def planka_macro(d):
    """macro-F1 у той же сильнейшей константы.

    Константа берёт один класс: по нему полнота 1, по остальным нули. Число
    получается низкое — и это честно показывает, почему accuracy при перекосе
    классов обманывает, а macro-F1 нет.
    """
    cm = d.get("confusion", [])
    if not cm: return 0.0
    sums = [sum(r) for r in cm]
    n = max(sum(sums), 1)
    p = max(sums) / n                      # точность константы = доля этого класса
    return (2 * p / (p + 1)) / len(sums)   # F1 по нему, остальные нули


def f1_by_class(d):
    """F1 по классам из матрицы ошибок."""
    lab, cm = d.get("labels", []), d.get("confusion", [])
    out = {}
    for i, c in enumerate(lab):
        tp = cm[i][i]
        fp = sum(cm[j][i] for j in range(len(lab))) - tp
        fn = sum(cm[i]) - tp
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        out[c] = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    return out


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "results", "*.json")))
    if not files:
        print("папки results/ с результатами нет — ни один запуск ещё не закончился")
        return
    R = {}
    for p in files:
        d = json.load(open(p, encoding="utf-8"))
        # В results/ лежат не только результаты обучения: export_onnx.py кладёт туда
        # onnx_validation.json, где ни accuracy, ни матрицы ошибок нет. Берём только
        # то, что действительно является результатом запуска.
        if "accuracy" not in d or "confusion" not in d:
            continue
        R[os.path.splitext(os.path.basename(p))[0]] = d
    if not R:
        print("в results/ нет ни одного результата обучения")
        return

    print("=" * 92)
    print("ВСЕ ЗАКОНЧЕННЫЕ ЗАПУСКИ")
    print("=" * 92)
    print(f"{'запуск':18s} {'accuracy':>9s} {'к константе':>12s} "
          f"{'macro-F1':>9s} {'к константе':>12s}   {'F1 feeding':>10s} {'alert':>6s} {'empty':>6s}")
    for name, d in R.items():
        base, bmac = planka(d), planka_macro(d)
        f1 = f1_by_class(d)
        print(f"{name:18s} {d['accuracy']:9.3f} {d['accuracy']-base:+12.3f} "
              f"{d['macro_f1']:9.3f} {d['macro_f1']-bmac:+12.3f}   "
              f"{f1.get('feeding',0):10.3f} {f1.get('alert',0):6.3f} {f1.get('empty',0):6.3f}")
        print(f"{'':18s} {SMYSL.get(name,'')}")
    any_d = next(iter(R.values()))
    print(f"\n  константа «всегда самый частый класс»: accuracy {planka(any_d):.3f}, "
          f"macro-F1 {planka_macro(any_d):.3f}")
    print("  По accuracy константу перебить трудно из-за перекоса классов,")
    print("  по macro-F1 — видно, учит ли модель хоть что-то. Смотреть надо на оба.")

    print("\n" + "=" * 92)
    print("СРАВНЕНИЯ — ЭТО И ЕСТЬ ЭКСПЕРИМЕНТЫ")
    print("=" * 92)
    for a, b, what in PARY:
        if a in R and b in R:
            da, db = R[a]["accuracy"], R[b]["accuracy"]
            ma, mb = R[a]["macro_f1"], R[b]["macro_f1"]
            print(f"\n  {what}")
            print(f"    {a:18s} accuracy {da:.3f}   macro-F1 {ma:.3f}")
            print(f"    {b:18s} accuracy {db:.3f}   macro-F1 {mb:.3f}")
            print(f"    разница          {db-da:+.3f}          {mb-ma:+.3f}")
        else:
            missing = [x for x in (a, b) if x not in R]
            print(f"\n  {what}\n    ещё не готово: {', '.join(missing)}")

    # Планка: у нечестного датасета своя, и сравнивать надо выигрыши, а не accuracy.
    if "small_100_random" in R and "small_100" in R:
        h, r = R["small_100"], R["small_100_random"]
        hb, rb = planka(h), planka(r)
        print("\n" + "=" * 92)
        print("ЦЕНА ПСЕВДОРЕПЛИКАЦИИ — главное число отчёта")
        print("=" * 92)
        print(f"  {'деление':22s} {'accuracy':>9s} {'своя планка':>12s} {'выигрыш':>9s}")
        print(f"  {'по клипам (честно)':22s} {h['accuracy']:9.3f} {hb:12.3f} {h['accuracy']-hb:+9.3f}")
        print(f"  {'по кадрам (нечестно)':22s} {r['accuracy']:9.3f} {rb:12.3f} {r['accuracy']-rb:+9.3f}")
        print(f"\n  разрыв по accuracy: {r['accuracy']-h['accuracy']:+.3f}")
        print("  Те же кадры, та же модель, те же эпохи. Отличается только способ деления.")

    print("\nчего ещё нет:",
          ", ".join(n for n in SMYSL if n not in R) or "всё готово")


if __name__ == "__main__":
    main()
