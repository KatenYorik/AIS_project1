"""
Шаг 2: разложенные по папкам кадры → датасет для YOLO-классификации.

Структура на выходе (та, которую ultralytics ожидает для classify):

    datasets/birds_v1/
      train/{feeding,alert,empty}/*.jpg
      val/{feeding,alert,empty}/*.jpg

Папка ambiguous в датасет не попадает — она нужна для отчёта, а не для обучения.

------------------------------------------------------------------------------
ВНИМАНИЕ: одну функцию здесь пишешь ты, а не я. Это `split_by_clip`.

Причина не в лени, а в том, что именно в этой функции живёт главная
концептуальная ошибка всей задачи. Если разбить кадры на train/val случайно,
то почти одинаковые соседние кадры одного клипа попадут и туда, и туда;
модель фактически увидит валидацию на обучении, точность окажется завышенной,
и результат работы будет неверным при формально правильном коде.

Пока функция не написана, `--check` будет падать. Спецификация — в её docstring.
Помощник по этой функции: python split_help.py (обзор, кирпичики, подсказки,
тесты по одному с разбором каждого падения).
------------------------------------------------------------------------------

Использование:
    python split_help.py                                # помощник: с чего начать
    python dataset.py --check                           # прогнать тесты своей функции
    python dataset.py --sorted sorted_course3 --out datasets/birds_v1_course3
"""
from __future__ import annotations

import sys as _sys, pathlib as _pl  # общие пути AIS, см. common/aispaths.py
_sys.path.insert(0, str(next(_p / "common" for _p in _pl.Path(__file__).resolve().parents
                            if (_p / "common" / "aispaths.py").is_file())))
import aispaths
aispaths.to_data()  # данные, runs, results и пути в аргументах — от AIS/data
import argparse
import collections
import os
import random
import shutil
import sys

from extract_frames import parse_frame_name

CLASSES = ["feeding", "alert", "empty"]      # ambiguous намеренно отсутствует


# ============================================================== ТВОЯ ФУНКЦИЯ
def split_by_clip(files: list[str], val_frac: float = 0.25,
                  seed: int = 0) -> tuple[list[str], list[str]]:
    """Разбить кадры на обучающую и валидационную выборки ПО КЛИПАМ.

    Вход:
        files     — список путей к кадрам. Имя каждого файла имеет вид
                    <клип>_t<номер>.jpg, разбирается через parse_frame_name.
        val_frac  — какую примерно долю КЛИПОВ (не кадров) отдать в валидацию.
        seed      — для воспроизводимости.

    Выход:
        (train_files, val_files)

    Требования, которые проверяет --check:
        1. Ни один клип не встречается одновременно в train и в val.
           Это главное требование, ради него всё и затевалось.
        2. Объединение train и val равно исходному списку, пересечение пусто.
        3. Обе выборки непусты, если клипов хотя бы два.
        4. При одном и том же seed результат одинаков.
        5. Доля клипов в val близка к val_frac (в пределах одного клипа).

    Подсказка по устройству (не по коду):
        сгруппировать файлы по идентификатору клипа → перемешать список
        идентификаторов с фиксированным seed → отрезать первые k штук в val,
        где k = round(val_frac * числа клипов), но не меньше 1 и не больше
        числа клипов минус 1 → собрать файлы обратно.
    """
    groups = collections.defaultdict(list)
    for f in files:
        groups[parse_frame_name(f)[0]].append(f)

    clips = sorted(groups)
    random.Random(seed).shuffle(clips)

    k = max(1, min(round(val_frac * len(clips)), len(clips) - 1))
    control = [f for a in clips[:k] for f in groups[a]]
    main = [f for a in clips[k:] for f in groups[a]]

    return main, control
# ==========================================================================


def build(sorted_dir: str, out_dir: str, val_frac: float, seed: int) -> dict:
    """Собрать датасет: скопировать кадры в train/ и val/ по классам.

    Важная тонкость. Разбиение считается ОДИН раз по всем кадрам сразу, а не
    отдельно внутри каждого класса. Если звать split_by_clip для каждого класса
    по очереди, наборы клипов у классов разные (например, класс empty есть не во
    всех клипах), перемешивание даёт разный порядок, и один и тот же клип может
    угодить в train для одного класса и в val для другого. Тогда audit() честно
    упадёт с ошибкой — и правильно сделает.
    """
    stats = {}
    for split in ("train", "val"):
        for c in CLASSES:
            os.makedirs(os.path.join(out_dir, split, c), exist_ok=True)

    # 1. собрать все кадры разом, запомнив класс каждого
    all_files, cls_of = [], {}
    for c in CLASSES:
        src = os.path.join(sorted_dir, c)
        if not os.path.isdir(src):
            print(f"  предупреждение: нет папки {src}")
            stats[c] = (0, 0)
            continue
        for f in sorted(os.listdir(src)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                p = os.path.join(src, f)
                all_files.append(p); cls_of[p] = c
    if not all_files:
        print("  кадров не найдено"); return stats

    # 2. один вызов твоей функции на весь датасет
    tr, va = split_by_clip(all_files, val_frac, seed)

    # 3. разложить по классам согласно полученному разбиению
    counts = {c: [0, 0] for c in CLASSES}
    for split, group in (("train", tr), ("val", va)):
        i = 0 if split == "train" else 1
        for f in group:
            c = cls_of[f]
            shutil.copy2(f, os.path.join(out_dir, split, c, os.path.basename(f)))
            counts[c][i] += 1
    for c in CLASSES:
        stats[c] = tuple(counts[c])
        if sum(counts[c]) == 0:
            print(f"  предупреждение: класс {c} пуст")
    return stats


def audit(out_dir: str) -> None:
    """Проверка собранного датасета: пересечение клипов между train и val.

    Запускается всегда после сборки. Если здесь что-то напечатается красным —
    значит датасет непригоден, и все метрики после него будут завышены.
    """
    clips = {}
    for split in ("train", "val"):
        s = set()
        for c in CLASSES:
            d = os.path.join(out_dir, split, c)
            for f in os.listdir(d):
                s.add(parse_frame_name(f)[0])
        clips[split] = s
    overlap = clips["train"] & clips["val"]
    print(f"\nКлипов в train: {len(clips['train'])}, в val: {len(clips['val'])}")
    if overlap:
        print(f"  ОШИБКА: клипы в обеих выборках: {sorted(overlap)}")
        print("  Датасет непригоден — метрики будут завышены.")
        sys.exit(1)
    print("  Пересечения по клипам нет — датасет корректен.")


# ============================================================== тесты
def _fake(clips: dict[str, int]) -> list[str]:
    """Сгенерировать фиктивные имена кадров: {'clip01': 10} → 10 кадров этого клипа."""
    return [f"/tmp/{cid}_t{i:05d}.jpg" for cid, n in clips.items() for i in range(n)]


def check() -> None:
    files = _fake({"clipA": 20, "clipB": 15, "clipC": 30, "clipD": 5})

    tr, va = split_by_clip(files, val_frac=0.25, seed=0)

    # 2. разбиение — это именно разбиение
    assert set(tr) | set(va) == set(files), "часть кадров потеряна или добавлена"
    assert not (set(tr) & set(va)), "кадр попал в обе выборки"

    # 1. главное требование
    ctr = {parse_frame_name(f)[0] for f in tr}
    cva = {parse_frame_name(f)[0] for f in va}
    assert not (ctr & cva), f"клипы в обеих выборках: {ctr & cva}"

    # 3. обе непусты
    assert tr and va, "одна из выборок пуста"

    # 4. воспроизводимость
    assert split_by_clip(files, 0.25, 0) == (tr, va), "результат не воспроизводится"
    # и разный seed обычно даёт другое разбиение
    assert any(split_by_clip(files, 0.25, s)[1] != va for s in range(1, 6)), \
        "seed ни на что не влияет"

    # 5. доля клипов примерно та, что просили
    assert abs(len(cva) - 0.25 * 4) <= 1, f"в val {len(cva)} клипов из 4, ожидалось ~1"

    # крайний случай: два клипа — по одному в каждую выборку
    tr2, va2 = split_by_clip(_fake({"x": 3, "y": 3}), val_frac=0.5, seed=0)
    assert tr2 and va2, "при двух клипах обе выборки должны быть непусты"

    # проверка, что делится именно по клипам, а не по кадрам:
    # если бы делили случайно, при 4 клипах пересечение было бы почти наверняка
    print("dataset.py: все проверки пройдены. Функция написана верно.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="прогнать тесты split_by_clip")
    ap.add_argument("--sorted", default="frames/sorted")
    ap.add_argument("--out", default="datasets/birds_v1")
    ap.add_argument("--val-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--classes", default="",
                    help="через запятую, либо auto — взять имена папок из --sorted")
    a = ap.parse_args()

    # Набор классов по умолчанию — три зачётных. Но этим же скриптом собирается
    # и набор для предобучения, где классы другие (виды птиц), поэтому его можно
    # задать явно или прочитать с диска.
    if a.classes:
        global CLASSES
        CLASSES = ([d for d in sorted(os.listdir(a.sorted))
                    if os.path.isdir(os.path.join(a.sorted, d))]
                   if a.classes == "auto"
                   else [s.strip() for s in a.classes.split(",") if s.strip()])
        print(f"классы: {CLASSES}")

    if a.check:
        check()
        return

    stats = build(a.sorted, a.out, a.val_frac, a.seed)
    print(f"\nДатасет: {a.out}")
    total = collections.Counter()
    for c, (n_tr, n_va) in stats.items():
        print(f"  {c:10s} train {n_tr:4d}   val {n_va:4d}")
        total["train"] += n_tr; total["val"] += n_va
    print(f"  {'итого':10s} train {total['train']:4d}   val {total['val']:4d}")

    # Базовое решение «самый частый класс» — одна строка, а придаёт смысл
    # всем последующим числам модели.
    if total["val"]:
        biggest = max(stats.values(), key=lambda x: x[1])[1]
        print(f"\nБазовое решение (самый частый класс) на val: "
              f"{biggest / total['val']:.3f}")

    audit(a.out)


if __name__ == "__main__":
    main()
