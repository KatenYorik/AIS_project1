# -*- coding: utf-8 -*-
"""Помощник по шагу 2: написать split_by_clip.

Эту функцию я намеренно не пишу за тебя — в ней живёт главная ошибка всей задачи.
Но всё вокруг неё можно автоматизировать, и здесь это сделано.

    python split_help.py             с чего начать: твои клипы и почему нельзя делить кадры
    python split_help.py --tools     кирпичики стандартной библиотеки, каждый отдельно
    python split_help.py --hint 1    подсказки нарастающей силы: 1, 2, 3
    python split_help.py --cpp       тот же алгоритм на C++ и словарь C++ -> питон
    python split_help.py --check     тесты ПО ОДНОМУ, с разбором каждого падения
    python split_help.py --result    что выходит на настоящих 16 клипах (без копирования)
    python split_help.py --result --seeds 10     сравнить десять зёрен и выбрать

Ничего не копирует и не портит: только читает имена файлов.
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

import argparse, collections, os, random

ROOT = str(aispaths.DATA)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CLASSES = ["feeding", "alert", "empty"]


def head(s):
    print("\n" + "=" * 72); print(s); print("=" * 72)


def sub(s):
    print("\n--- " + s + " " + "-" * max(0, 66 - len(s)))


# ------------------------------------------------------------------ материал
def real_files(sorted_dir="sorted_course3"):
    """Настоящие кадры со схемой из трёх классов: {файл: класс}. Только имена."""
    d = os.path.join(ROOT, sorted_dir)
    out = {}
    if not os.path.isdir(d): return out
    for c in CLASSES:
        p = os.path.join(d, c)
        if not os.path.isdir(p): continue
        for f in sorted(os.listdir(p)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                out[os.path.join(p, f)] = c
    return out


def clip_of(path):
    return os.path.splitext(os.path.basename(path))[0].rsplit("_t", 1)[0]


def fake(clips: dict) -> list:
    return [f"/tmp/{cid}_t{i:05d}.jpg" for cid, n in clips.items() for i in range(n)]


# ------------------------------------------------------------------ обзор
def overview():
    head("ШАГ 2. ТВОЯ ФУНКЦИЯ split_by_clip")
    print("""
Где: project1\\step2_dataset\\dataset.py, рамка «ТВОЯ ФУНКЦИЯ». Сейчас там NotImplementedError.

    split_by_clip(files, val_frac=0.25, seed=0) -> (train_files, val_files)

Вход  — список путей к кадрам вида <клип>_t<номер>.jpg
Выход — два списка: на чём учить и на чём проверять""")

    files = real_files()
    if not files:
        print("\nПапки sorted_course3 нет — сначала прогони  python prepare_data.py")
        print("Дальше можно и без неё: --tools, --hint и --check работают всегда.")
        return

    sub("твой материал: 16 клипов, именно они и делятся")
    by = collections.defaultdict(collections.Counter)
    for f, c in files.items(): by[clip_of(f)][c] += 1
    print(f"    {'клип':22s} {'кадров':>7s} {'feeding':>8s} {'alert':>6s} {'empty':>6s}")
    for cid in sorted(by, key=lambda k: -sum(by[k].values())):
        n = sum(by[cid].values())
        print(f"    {cid:22s} {n:7d} {by[cid]['feeding']:8d} "
              f"{by[cid]['alert']:6d} {by[cid]['empty']:6d}")
    print(f"    {'ИТОГО':22s} {len(files):7d}  клипов: {len(by)}")
    sizes = sorted(sum(v.values()) for v in by.values())
    print(f"\n  Клипы от {sizes[0]} до {sizes[-1]} кадров — запомни это, дальше пригодится.")

    # Главная демонстрация: что будет, если делить кадры, а не клипы.
    sub("почему нельзя делить кадры случайно — проверка на твоих данных")
    lst = sorted(files)
    rnd = random.Random(0); rnd.shuffle(lst)
    k = int(0.25 * len(lst))
    va, tr = set(lst[:k]), set(lst[k:])
    both = {clip_of(f) for f in va} & {clip_of(f) for f in tr}
    print(f"  случайно отобрали 25 % кадров ({k} штук) в валидацию")
    print(f"  клипов, попавших СРАЗУ В ОБЕ выборки: {len(both)} из {len(by)}")
    print("""
  То есть модель на проверке увидит те же клипы, на которых училась: ту же птицу,
  ту же ветку, тот же свет, позу на полградуса другую. Кадры нарезаны два раза в
  секунду, соседние — почти одна картинка.

  Точность при этом вырастет, ничего не упадёт, код останется формально верным.
  Именно поэтому ошибку и не видно — её надо не заметить, а не поймать.

  Правильное разбиение даёт в этой строке 0. Это и есть твоя задача.""")

    # Доля кадров гуляет, потому что клипы разной длины.
    sub("почему val_frac — про клипы, а не про кадры")
    names = sorted(by)
    fr = []
    for s in range(300):
        r = random.Random(s); order = names[:]; r.shuffle(order)
        sel = set(order[:round(0.25 * len(names))])
        fr.append(sum(sum(by[c].values()) for c in sel) / len(files))
    fr.sort()
    print(f"  отдаём в валидацию 4 клипа из 16 (это 25 % клипов),")
    print(f"  а доля КАДРОВ при этом гуляет от {fr[0]:.0%} до {fr[-1]:.0%}, "
          f"типично {fr[len(fr)//2]:.0%}")
    print("  Потому что клипы разной длины. Считать долю от кадров — первая из")
    print("  типичных ошибок; функция должна отбирать именно клипы.")

    print("""
Дальше:
    python split_help.py --tools     чем это делается: четыре кирпичика
    python split_help.py --hint 1    подсказка, если непонятно с чего начать
    python split_help.py --cpp       тот же алгоритм на C++ и словарь C++ -> питон
    python split_help.py --check     проверить написанное, тесты по одному""")


# ------------------------------------------------------------------ кирпичики
def tools():
    head("КИРПИЧИКИ. Каждый отдельно, на посторонних данных")
    print("Складывать их в правильном порядке — твоя часть работы, в ней вся задача.")

    sub("1. узнать клип по имени файла — готовая функция проекта")
    try:
        from extract_frames import parse_frame_name
        for n in ("kormushka2672_t00135.jpg", "snegir2692_t00042.jpg"):
            print(f"    parse_frame_name({n!r})")
            print(f"      -> {parse_frame_name(n)}      [0] — клип, [1] — секунда")
    except Exception as e:
        print(f"    (не удалось импортировать: {e})")

    sub("2. сгруппировать список по признаку — collections.defaultdict")
    print("""    Пример НЕ про кадры, чтобы было видно только приём:

        import collections
        d = collections.defaultdict(list)
        for w in ["ёж", "ель", "кот", "куст", "ель"]:
            d[w[0]].append(w)          # ключ — первая буква""")
    d = collections.defaultdict(list)
    for w in ["ёж", "ель", "кот", "куст", "ель"]: d[w[0]].append(w)
    print(f"      -> {dict(d)}")
    print("    defaultdict(list) сам заводит пустой список под новый ключ.")

    sub("3. перемешать воспроизводимо — random.Random(seed)")
    print("""        rnd = random.Random(seed)
        rnd.shuffle(мой_список)        # перемешивает НА МЕСТЕ, ничего не возвращает""")
    for s in (0, 0, 1):
        x = list("ABCDEFGH"); random.Random(s).shuffle(x)
        print(f"      seed={s}: {''.join(x)}")
    print("    Одинаковое зерно — одинаковый порядок, всегда и на любой машине.")
    print("    random.shuffle без зерна так не умеет, и тест на воспроизводимость это ловит.")

    sub("4. отрезать первые k и остальное — срезы")
    x = list("ABCDEFGH")
    print(f"        x = {x}")
    print(f"        x[:3] -> {x[:3]}        x[3:] -> {x[3:]}")
    print("    Вместе они дают ровно исходный список, без потерь и повторов.")

    sub("5. сколько клипов брать — округление с ограничителями")
    print("    Правило словами: округлить val_frac × число клипов,")
    print("    но не меньше 1 и не больше «число клипов минус 1».")
    print(f"\n    {'клипов':>8s} {'val_frac':>9s} {'округление':>11s} {'должно выйти':>13s}")
    for n, vf in ((16, 0.25), (16, 0.30), (4, 0.25), (2, 0.5), (16, 0.02), (3, 0.9)):
        r = round(vf * n)
        print(f"    {n:8d} {vf:9.2f} {r:11d} {max(1, min(r, n - 1)):13d}")
    print("\n    Две последние строки — ровно те, ради которых нужны ограничители:")
    print("    без них одна из выборок оказалась бы пустой, и тесты это проверяют.")
    print("\n    Функции round, max, min встроенные, импортировать ничего не надо.")

    print("\nЭто всё, что требуется. Ни одного экзотического приёма здесь нет.")


# ------------------------------------------------------------------ подсказки
def hint(level):
    if level == 1:
        head("ПОДСКАЗКА 1. С чего начать думать")
        print("""
Забудь про питон на минуту и ответь на вопрос словами: что физически должно
оказаться в валидации?

Не «четверть кадров». Четыре КЛИПА целиком — со всеми своими кадрами, от первого
до последнего. Остальные двенадцать клипов целиком уходят в обучение. Ни один клип
не разрезается пополам, никогда.

Значит и решение принимается не про кадр, а про клип: сначала выбираются клипы,
и только потом под них подтягиваются файлы.

Отсюда порядок сам собой: узнать, какие вообще есть клипы → выбрать из них те,
что пойдут в проверку → собрать файлы выбранных в один список, файлы остальных в
другой.

Эффективность не важна: у тебя 792 файла и 16 клипов, любой перебор мгновенный.

    python split_help.py --hint 2      что именно делать, по действиям""")

    elif level == 2:
        head("ПОДСКАЗКА 2. Четыре действия и что должно получиться после каждого")
        print("""
1. СГРУППИРОВАТЬ файлы по клипу.
   Пройти список files, у каждого файла узнать клип через parse_frame_name(f)[0],
   складывать файлы в словарь «клип → список его файлов».
   После этого действия: словарь из 16 ключей, в сумме 792 файла.

2. ПЕРЕМЕШАТЬ СПИСОК КЛИПОВ — не файлов, а именно имён клипов, и воспроизводимо,
   генератором random.Random(seed).
   После: список из 16 имён в другом порядке. Файлы пока не трогаем вообще.

3. ОТРЕЗАТЬ первые k имён в валидацию, где k = round(val_frac × 16) = 4,
   с ограничителями «не меньше 1, не больше 15».
   После: 4 имени в одном списке, 12 в другом.

4. СОБРАТЬ ФАЙЛЫ обратно: все файлы четырёх выбранных клипов — в val,
   все файлы остальных двенадцати — в train, вернуть (train, val).
   После: два списка, в сумме снова 792 файла, ни одного лишнего и ни одного
   потерянного. Порядок «сначала train, потом val» — так объявлено в сигнатуре.

Проверить себя можно не запуская обучение:
    python split_help.py --check       тесты
    python split_help.py --result      что вышло на настоящих клипах

    python split_help.py --hint 3      псевдокод, если действия ясны, а запись нет""")

    else:
        head("ПОДСКАЗКА 3. Псевдокод. Дальше подсказок не будет")
        print("""
Это не питон, это запись словами — переводить на питон тебе.

    функция split_by_clip(files, val_frac, seed):

        группы = пустой словарь «клип -> список файлов»
        для каждого f из files:
            клип = parse_frame_name(f)[0]
            добавить f в группы[клип]

        имена = ОТСОРТИРОВАННЫЙ список ключей словаря
        перемешать имена генератором random.Random(seed)

        k = round(val_frac * количество имён)
        зажать k между 1 и (количество имён - 1)

        val_клипы   = первые k имён
        train_клипы = все остальные имена

        вернуть (файлы всех train_клипов, файлы всех val_клипов)

Одна тонкость, которой нет в спецификации, но она важна: ключи словаря стоит
именно ОТСОРТИРОВАТЬ перед перемешиванием. Порядок ключей зависит от того, в каком
порядке файлы пришли на вход, а он зависит от файловой системы. Отсортировал —
и результат зависит только от seed, как и обещано в тестах.

Когда напишешь:
    python split_help.py --check""")


# ------------------------------------------------------------------ через C++
def cpp():
    head("ТОТ ЖЕ АЛГОРИТМ НА C++ И СЛОВАРЬ ПЕРЕВОДА")
    print("""
Если C++ читается легче питона — вот работающая версия на нём. Питон отсюда
получается почти построчно, но не дословно: два места устроены по-разному, и они
отмечены в словаре ниже.

    std::pair<std::vector<std::string>, std::vector<std::string>>
    split_by_clip(const std::vector<std::string>& files,
                  double val_frac = 0.25, unsigned seed = 0)
    {
        // 1. клип -> его файлы
        std::map<std::string, std::vector<std::string>> groups;
        for (const auto& f : files)
            groups[clip_of(f)].push_back(f);

        // 2. список имён клипов, перемешанный воспроизводимо
        std::vector<std::string> names;
        for (const auto& [name, _] : groups)
            names.push_back(name);
        std::shuffle(names.begin(), names.end(), std::mt19937(seed));

        // 3. сколько клипов в валидацию, с ограничителями
        size_t n = names.size();
        size_t k = static_cast<size_t>(std::llround(val_frac * n));
        k = std::max<size_t>(1, std::min(k, n - 1));

        // 4. собрать файлы обратно
        std::vector<std::string> train, val;
        for (size_t i = 0; i < n; ++i)
            for (const auto& f : groups[names[i]])
                (i < k ? val : train).push_back(f);

        return {train, val};
    }""")

    sub("словарь: C++ -> питон")
    rows = [
        ("std::map<std::string, std::vector<std::string>> g;",
         "g = collections.defaultdict(list)"),
        ("g[key].push_back(f);", "g[key].append(f)"),
        ("clip_of(f)", "parse_frame_name(f)[0]"),
        ("перебор ключей std::map", "names = sorted(g)      <- ВНИМАНИЕ, см. ниже"),
        ("std::shuffle(v.begin(), v.end(), std::mt19937(seed));",
         "random.Random(seed).shuffle(v)"),
        ("std::llround(x)", "round(x)"),
        ("std::max<size_t>(1, std::min(k, n - 1))", "max(1, min(k, n - 1))"),
        ("names[0..k) и names[k..n)", "names[:k] и names[k:]"),
        ("return {train, val};", "return train, val"),
        ("std::vector<std::string> train, val;", "train, val = [], []"),
        ("for (const auto& f : xs) ys.push_back(f);", "ys.extend(xs)"),
    ]
    w = max(len(a) for a, _ in rows)
    for a, b in rows:
        print(f"    {a:{w}s}   ->   {b}")

    sub("два места, где перевод НЕ дословный")
    print("""
1. std::map держит ключи ОТСОРТИРОВАННЫМИ, а питоновский dict — в порядке
   добавления. Порядок добавления зависит от того, как файлы легли на диск.
   Поэтому в питоне ключи надо отсортировать явно: sorted(g). Иначе результат
   будет зависеть не только от seed, и тест на воспроизводимость это поймает.

2. std::mt19937(seed) и random.Random(seed) — разные генераторы. Оба
   воспроизводимы, но перестановки дадут разные. Для задачи это безразлично:
   требуется «одинаково при одинаковом seed», а не «как в C++».

Ещё мелочи, на которых спотыкаются, приходя из C++:

    отступы вместо { }           блок задаётся только отступом, четыре пробела
    типы не пишутся              def split_by_clip(files, val_frac=0.25, seed=0):
    нет ; в конце строк
    v[:k] возвращает КОПИЮ       срез не ссылка, исходный список цел
    shuffle меняет список НА МЕСТЕ и возвращает None:
        names = random.shuffle(names)   <- так names станет None, частая ошибка
        random.Random(seed).shuffle(names)          <- так правильно

Проверить перевод:  python split_help.py --check""")


# ------------------------------------------------------------------ проверка
def load():
    """Импортировать dataset.py и убедиться, что функция вообще написана."""
    try:
        import dataset
    except Exception as e:
        print(f"\nНе удалось загрузить dataset.py: {type(e).__name__}: {e}")
        print("Скорее всего опечатка в файле — питон не смог его прочитать целиком.")
        return None
    try:
        dataset.split_by_clip(fake({"a": 2, "b": 2}), 0.5, 0)
    except NotImplementedError:
        head("ФУНКЦИЯ ЕЩЁ НЕ НАПИСАНА")
        print("""
В dataset.py, в рамке «ТВОЯ ФУНКЦИЯ», по-прежнему стоит raise NotImplementedError.
Убери эту строку и напиши тело функции.

    python split_help.py --hint 1     с чего начать
    python split_help.py --tools      чем это делается""")
        return None
    except Exception:
        pass          # падает — разберём в тестах, по одному
    return dataset


CASES = []


def case(name, mistake=""):
    def deco(fn):
        CASES.append((name, fn, mistake, fn.__doc__ or ""))
        return fn
    return deco


@case("возвращает пару списков")
def t_shape(f):
    """Функция должна вернуть кортеж из двух списков: (train, val).
    Если вернулся один список, None или что-то ещё — build() не сможет их разложить."""
    r = f(fake({"a": 3, "b": 3, "c": 3, "d": 3}), 0.25, 0)
    assert isinstance(r, tuple) and len(r) == 2, f"вернулось {type(r).__name__}, а нужен кортеж из двух"
    tr, va = r
    assert isinstance(tr, list) and isinstance(va, list), "внутри кортежа должны быть списки"


@case("ничего не потеряно и не задвоено")
def t_partition(f):
    """train и val вместе должны давать ровно исходный список: каждый кадр ровно один раз.
    Потеря — часть данных пропала. Задвоение — кадр попал в обе выборки или скопируется дважды."""
    files = fake({"a": 3, "b": 3, "c": 3, "d": 3})
    tr, va = f(files, 0.25, 0)
    lost = set(files) - set(tr) - set(va)
    extra = (set(tr) | set(va)) - set(files)
    assert not lost, f"потеряно кадров: {len(lost)}, например {sorted(lost)[:2]}"
    assert not extra, f"появились лишние кадры: {sorted(extra)[:2]}"
    assert not (set(tr) & set(va)), "кадр попал сразу в обе выборки"
    assert len(tr) + len(va) == len(files), \
        f"кадров на выходе {len(tr) + len(va)}, а на входе {len(files)} — где-то повтор"


@case("ни один клип не в обеих выборках", "делили кадры, а не клипы")
def t_main(f):
    """ГЛАВНОЕ ТРЕБОВАНИЕ. Клип целиком либо в обучении, либо в проверке.
    Если этот тест падает — почти наверняка перемешивался список файлов, а не список клипов."""
    files = fake({"a": 20, "b": 15, "c": 30, "d": 5})
    tr, va = f(files, 0.25, 0)
    both = {clip_of(x) for x in tr} & {clip_of(x) for x in va}
    assert not both, f"клипы в обеих выборках: {sorted(both)}"


@case("обе выборки непусты")
def t_nonempty(f):
    """Если val пуста — проверять не на чем. Если пуст train — учить не на чем."""
    tr, va = f(fake({"a": 20, "b": 15, "c": 30, "d": 5}), 0.25, 0)
    assert tr, "train пуст"
    assert va, "val пуст"


@case("тот же seed — тот же результат", "перемешивание без зерна")
def t_repro(f):
    """Два вызова с одинаковыми аргументами обязаны дать одинаковое разбиение.
    Иначе результаты двух запусков обучения несравнимы: менялась не модель, а данные."""
    files = fake({"a": 20, "b": 15, "c": 30, "d": 5})
    a1 = f(files, 0.25, 0); a2 = f(files, 0.25, 0)
    if a1 != a2 and [set(x) for x in a1] == [set(x) for x in a2]:
        raise AssertionError(
            "состав выборок тот же, но порядок файлов внутри списков разный. "
            "Обычно это значит, что перемешивался сам список files (на месте), "
            "а не список клипов")
    assert a1 == a2, "два одинаковых вызова дали разные разбиения — где-то random без зерна"


@case("другой seed — обычно другое разбиение")
def t_seed(f):
    """Если seed ни на что не влияет, значит перемешивания нет вовсе: берутся, скажем,
    первые клипы по алфавиту. Формально не смертельно, но seed тогда обманывает."""
    files = fake({"a": 20, "b": 15, "c": 30, "d": 5})
    base = f(files, 0.25, 0)[1]
    assert any(f(files, 0.25, s)[1] != base for s in range(1, 6)), \
        "пять разных зёрен дали одно и то же — перемешивания нет"


@case("доля клипов близка к val_frac", "считали долю от кадров")
def t_frac(f):
    """val_frac — доля КЛИПОВ. На четырёх клипах и 0.25 должен получиться один клип.
    Если получилось больше — скорее всего доля считалась от числа кадров."""
    files = fake({"a": 20, "b": 15, "c": 30, "d": 5})
    va = f(files, 0.25, 0)[1]
    n = len({clip_of(x) for x in va})
    assert abs(n - 1) <= 0, f"в val {n} клипов из 4, а ожидался 1"


@case("крайний случай: два клипа", "забыты ограничители на k")
def t_two(f):
    """Два клипа и val_frac=0.5: по одному в каждую выборку.
    Тут и вылезает отсутствие ограничителей — при round вниз val остаётся пустой."""
    tr, va = f(fake({"x": 3, "y": 3}), 0.5, 0)
    assert tr and va, "при двух клипах обе выборки должны быть непусты"


@case("крайний случай: очень маленькая доля", "забыты ограничители на k")
def t_tiny(f):
    """val_frac=0.02 при 16 клипах: round даёт 0, а выборка обязана быть непустой.
    Ограничитель «не меньше одного клипа» именно про это."""
    files = fake({f"c{i:02d}": 5 for i in range(16)})
    tr, va = f(files, 0.02, 0)
    assert va, "при очень малой доле val оказалась пуста — нет ограничителя «не меньше 1»"
    assert tr, "train пуст"


@case("реальный размер: 16 клипов, 0.25 -> 4 клипа")
def t_real(f):
    """Твой настоящий случай. Должно выйти ровно четыре клипа в валидации."""
    files = fake({f"c{i:02d}": 5 for i in range(16)})
    va = f(files, 0.25, 0)[1]
    n = len({clip_of(x) for x in va})
    assert n == 4, f"в val {n} клипов из 16, а ожидалось 4"


def check():
    ds = load()
    if ds is None: return 1
    head("ПРОВЕРКА ФУНКЦИИ, ТЕСТ ЗА ТЕСТОМ")
    bad = 0
    seen_crash = set()          # одну и ту же поломку разбираем один раз
    for i, (name, fn, mistake, doc) in enumerate(CASES, 1):
        try:
            fn(ds.split_by_clip)
            print(f"  [ok]   {i}. {name}")
        except AssertionError as e:
            bad += 1
            print(f"\n  [ПЛОХО] {i}. {name}")
            print(f"          {e}")
            for line in doc.strip().splitlines():
                print("          " + line.strip())
            if mistake: print(f"          типичная причина: {mistake}")
            print()
        except Exception as e:
            bad += 1
            key = f"{type(e).__name__}: {e}"
            if key in seen_crash:
                print(f"  [ОШИБКА] {i}. {name}: та же поломка")
                continue
            seen_crash.add(key)
            print(f"\n  [ОШИБКА] {i}. {name}: {key}")
            print("          Функция не доработала до конца — это не логика, а поломка кода.")
            import traceback
            tb = traceback.format_exc().strip().splitlines()
            for line in tb[-3:]: print("          " + line)
            print()

    # мягкая проверка: портит ли функция входной список
    files = fake({"a": 3, "b": 3, "c": 3})
    copy = list(files)
    try:
        ds.split_by_clip(files, 0.34, 0)
        if files != copy:
            print("\n  [!]    функция перемешала СВОЙ ВХОДНОЙ список (shuffle на месте).")
            print("         Тесты это пропускают, но привычка опасная: вызывающий код")
            print("         не ждёт, что его список изменится. Перемешивай копию или")
            print("         список клипов, а не files.")
    except Exception:
        pass

    print()
    if bad:
        print(f"Не пройдено: {bad} из {len(CASES)}.")
        print("Разбор типичных промахов — в ДО_СДАЧИ.ru.md, шаг 2.")
        print("Если застрял — покажи мне текст функции, подскажу, не дописывая.")
        return 1
    print("ВСЁ ПРОЙДЕНО. Функция верна.")
    print("\nДальше:")
    print("    python split_help.py --result     посмотреть на настоящих клипах")
    print("    python prepare_data.py            собрать датасеты и обучать")
    return 0


# ------------------------------------------------------------------ результат
def result(val_frac, seed, seeds):
    ds = load()
    if ds is None: return 1
    files = real_files()
    if not files:
        print("Нет папки sorted_course3 — сначала  python prepare_data.py")
        return 1

    def one(s):
        tr, va = ds.split_by_clip(sorted(files), val_frac, s)
        vc = sorted({clip_of(f) for f in va})
        cnt = collections.Counter(files[f] for f in va)
        return tr, va, vc, cnt

    if seeds:
        head(f"СРАВНЕНИЕ ЗЁРЕН (val_frac={val_frac})")
        print(f"  {'seed':>4s} {'клипов':>7s} {'кадров в val':>13s} {'доля':>6s}  "
              f"{'feeding':>7s} {'alert':>6s} {'empty':>6s}  клипы")
        rows = []
        for s in range(seeds):
            tr, va, vc, cnt = one(s)
            frac = len(va) / len(files)
            ok = 0.15 <= frac <= 0.40
            flag = "" if all(cnt[c] for c in CLASSES) else "  <- класс пуст!"
            print(f"  {s:4d} {len(vc):7d} {len(va):13d} {frac:6.0%}  "
                  f"{cnt['feeding']:7d} {cnt['alert']:6d} {cnt['empty']:6d}  "
                  f"{', '.join(vc)}{flag}")
            rows.append((s, frac, min(cnt[c] for c in CLASSES), ok))
        good = [r for r in rows if r[3]]
        if good:
            best = max(good, key=lambda r: r[2])
            print(f"""
  Совет: seed {best[0]} — доля кадров {best[1]:.0%}, и самый редкий класс представлен
  {best[2]} кадрами (это максимум среди подходящих зёрен). Взять его:

      python prepare_data.py --seed {best[0]}

  Дальше seed нигде указывать не надо: разбиение уже зашито в собранные папки,
  и все запуски обучения идут по нему.""")
        print("""
  Что выбирать: доля кадров в разумных пределах (примерно 0.15-0.40) и все три
  класса в валидации представлены не десятком кадров, а хоть сколько-нибудь.
  Менять seed ДО обучения нормально — это выбор разбиения. После обучения менять
  его уже нельзя: это подгонка под результат.""")
        return 0

    tr, va, vc, cnt = one(seed)
    head(f"РАЗБИЕНИЕ НА НАСТОЯЩИХ ДАННЫХ (val_frac={val_frac}, seed={seed})")
    both = {clip_of(f) for f in tr} & {clip_of(f) for f in va}
    print(f"  клипов в обеих выборках: {len(both)}" + ("  <- ОШИБКА!" if both else "   хорошо"))
    print(f"  кадров: train {len(tr)}, val {len(va)} — в валидации {len(va)/len(files):.0%}")
    print(f"\n  клипы, которые модель не увидит ({len(vc)}):")
    by = collections.defaultdict(collections.Counter)
    for f in va: by[clip_of(f)][files[f]] += 1
    for c in vc:
        n = sum(by[c].values())
        print(f"    {c:22s} {n:4d} кадров   feeding {by[c]['feeding']:3d}  "
              f"alert {by[c]['alert']:3d}  empty {by[c]['empty']:3d}")
    print(f"\n  классы в валидации: " +
          "  ".join(f"{c} {cnt[c]}" for c in CLASSES))
    if not all(cnt[c] for c in CLASSES):
        print("  ВНИМАНИЕ: класс пуст в валидации — метрика по нему не считается.")
        print("  Попробуй другой seed:  python split_help.py --result --seeds 10")
    print("\n  Один из этих клипов бери для демо с камерой — тогда демонстрация")
    print("  будет заодно честной проверкой на невиданных данных.")
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--tools", action="store_true", help="кирпичики стандартной библиотеки")
    ap.add_argument("--hint", type=int, choices=(1, 2, 3), help="подсказка 1, 2 или 3")
    ap.add_argument("--cpp", action="store_true", help="алгоритм на C++ и словарь перевода")
    ap.add_argument("--check", action="store_true", help="тесты по одному, с разбором")
    ap.add_argument("--result", action="store_true", help="разбиение на настоящих клипах")
    ap.add_argument("--val-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=0, help="сравнить N зёрен")
    a = ap.parse_args()

    if a.tools: return tools()
    if a.cpp: return cpp()
    if a.hint: return hint(a.hint)
    if a.check: sys.exit(check())
    if a.result: sys.exit(result(a.val_frac, a.seed, a.seeds))
    overview()


if __name__ == "__main__":
    main()
