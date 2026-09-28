# -*- coding: utf-8 -*-
"""Пример того же приёма на другой задаче — чтобы было от чего оттолкнуться.

    python primer_split.py

Задача-двойник. Есть полка книг, файлы называются  <автор>__<название>.txt
Надо отложить четверть АВТОРОВ в контрольную полку так, чтобы ни один автор не
оказался на обеих полках сразу.

Это ровно та же задача, что твоя, только вместо клипа — автор, а вместо кадра —
книга. Функция ниже написана целиком и работает: запусти и посмотри, что она
печатает после каждого из четырёх шагов.

Чем твоя функция будет отличаться — написано в самом низу файла. Отличий три, и
все три придётся сделать самому: механическое копирование не пройдёт тесты.
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

import collections
import random


def author_of(name: str) -> str:
    """Из имени файла достать автора: 'tolstoy__anna.txt' -> 'tolstoy'.

    У тебя эту роль играет parse_frame_name(f)[0] — она уже написана и
    импортирована в dataset.py, писать её не надо.
    """
    return name.split("__")[0]


def split_by_author(files: list[str], val_frac: float = 0.25,
                    seed: int = 0) -> tuple[list[str], list[str]]:
    """Разложить книги на две полки ПО АВТОРАМ: (основная, контрольная)."""

    # --- шаг 1: сгруппировать. Ключ — автор, значение — список его книг.
    # defaultdict(list) сам заводит пустой список под нового автора,
    # поэтому не нужно проверять «а есть ли уже такой ключ».
    groups = collections.defaultdict(list)
    for f in files:
        groups[author_of(f)].append(f)

    # --- шаг 2: взять список авторов и перемешать ЕГО, а не книги.
    # sorted нужен, чтобы порядок не зависел от того, в каком порядке пришли
    # файлы: словарь в питоне хранит ключи в порядке добавления.
    names = sorted(groups)
    random.Random(seed).shuffle(names)      # меняет список на месте

    # --- шаг 3: сколько авторов уходит в контроль.
    # round даёт «примерно четверть», а max/min не дают выборке опустеть,
    # если авторов совсем мало.
    k = round(val_frac * len(names))
    k = max(1, min(k, len(names) - 1))

    # --- шаг 4: собрать книги обратно по выбранным авторам.
    control = [f for a in names[:k] for f in groups[a]]
    main = [f for a in names[k:] for f in groups[a]]
    return main, control


# ------------------------------------------------------------------ показ
def demo():
    files = [
        "tolstoy__voina.txt", "tolstoy__anna.txt", "tolstoy__hadji.txt",
        "gogol__mertvye.txt", "gogol__shinel.txt",
        "chehov__chaika.txt", "chehov__vishnevyi.txt", "chehov__dama.txt",
        "pushkin__onegin.txt", "pushkin__mednyi.txt",
        "lermontov__geroi.txt", "lermontov__mtsyri.txt",
    ]
    print(f"на входе {len(files)} книг\n")

    groups = collections.defaultdict(list)
    for f in files:
        groups[author_of(f)].append(f)
    print("после шага 1 — словарь «автор -> его книги»:")
    for a, v in groups.items():
        print(f"    {a:12s} {len(v)} шт.  {v}")

    names = sorted(groups)
    print(f"\nпосле шага 2 — список авторов, отсортированный: {names}")
    random.Random(0).shuffle(names)
    print(f"                и он же перемешанный с seed=0:   {names}")

    k = max(1, min(round(0.25 * len(names)), len(names) - 1))
    print(f"\nпосле шага 3 — k = round(0.25 * {len(names)}) = {k}")
    print(f"    в контроль: {names[:k]}")
    print(f"    в основную: {names[k:]}")

    main, control = split_by_author(files, 0.25, 0)
    print(f"\nпосле шага 4 — {len(main)} книг и {len(control)} книг")
    print(f"    контрольная полка: {control}")

    a_main = {author_of(f) for f in main}
    a_ctrl = {author_of(f) for f in control}
    print(f"\nавторов на обеих полках сразу: {len(a_main & a_ctrl)}  <- ради этого всё")

    print("\nи ещё раз с разными зёрнами — тот же seed даёт тот же ответ всегда,")
    print("другой seed обычно (не обязательно всегда) даёт другой:")
    for s in (0, 0, 1, 2, 3):
        who = sorted({author_of(f) for f in split_by_author(files, 0.25, s)[1]})
        print(f"    seed={s}: {who}")

    print("""
------------------------------------------------------------------------------
ЧЕМ ТВОЯ ФУНКЦИЯ ОТЛИЧАЕТСЯ ОТ ЭТОЙ

1. Автор достаётся из имени по-другому. Здесь — split("__")[0]. У тебя имя
   выглядит как <клип>_t<номер>.jpg, и разбирает его готовая функция:
   parse_frame_name(f)[0]. Обрати внимание: на вход приходит полный ПУТЬ к файлу,
   а не голое имя, — parse_frame_name это учитывает сама.

2. Порядок возврата другой. Здесь возвращается (основная, контрольная).
   У тебя по сигнатуре — (train_files, val_files): сначала то, на чём учат,
   потом то, на чём проверяют. Перепутать легко, тесты это ловят сразу.

3. Проверок больше. Здесь одна ситуация — 5 авторов и четверть. У тебя тесты
   гоняют функцию и на двух клипах, и на шестнадцати, и с val_frac = 0.02.
   Ограничители max(1, min(...)) написаны как раз для этих случаев — посмотри
   на них внимательно и убедись, что понимаешь, зачем каждый из двух.

Дальше:  python split_help.py --check
------------------------------------------------------------------------------""")


if __name__ == "__main__":
    demo()
