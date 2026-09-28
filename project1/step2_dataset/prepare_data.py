# -*- coding: utf-8 -*-
"""Одна команда вместо пяти: от разметки до готовых датасетов.

    python prepare_data.py

Делает по порядку и с проверками на каждом шаге:

  1. инвентаризация — сколько кадров на диске, сколько меток, всё ли совпадает
  2. раскладка кадров по классам, сразу в обе схемы: три зачётных и шесть мелких
  3. проверка твоей функции split_by_clip
  4. сборка обоих датасетов и аудит на пересечение клипов
  5. сводка: базовое решение, какие клипы ушли в валидацию, что делать дальше

Если split_by_clip ещё не написана, скрипт честно останавливается после шага 2 и
объясняет, что делать. Ничего не ломается, повторный запуск безопасен: папки
пересоздаются с нуля.

    python prepare_data.py --only-sort     остановиться после раскладки
    python prepare_data.py --val-frac 0.3  другая доля клипов в валидации
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

import argparse, collections, csv, os, random, shutil, subprocess

ROOT = str(aispaths.DATA)


class Tee:
    """Печатать и в окно, и в файл.

    Окно консоли прокручивается и закрывается, а числа из сборки нужны потом:
    сколько получилось эпизодов, сколько кадров выбросила защитная полоса,
    какие клипы ушли в проверку. Теперь весь вывод остаётся в log_podgotovka.txt.
    """
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.out = sys.stdout

    def write(self, s):
        self.out.write(s); self.f.write(s); self.f.flush()

    def flush(self):
        self.out.flush(); self.f.flush()


COURSE3 = {"head_down": "feeding", "handling": "feeding",
           "head_up_ahead": "alert", "head_up_turnL": "alert",
           "head_up_turnR": "alert", "no_bird": "empty"}
FINE = list(COURSE3.keys())


def title(n, s):
    print("\n" + "=" * 70)
    print(f"ШАГ {n}. {s}")
    print("=" * 70)


def extra(s):
    """Заголовок дополнительного датасета — он не часть основной сборки."""
    print("\n" + "=" * 70)
    print("ДОПОЛНИТЕЛЬНО: " + s)
    print("=" * 70)


def die(msg, hint=""):
    print("\n" + "!" * 70)
    print(msg)
    if hint: print("\n" + hint)
    print("!" * 70)
    sys.exit(1)


# ---------------------------------------------------------------- 1
def inventory(labels_path):
    title(1, "ЧТО ЕСТЬ НА ДИСКЕ")
    if not os.path.exists(labels_path):
        die(f"не найден {os.path.basename(labels_path)}",
            "Он должен лежать в общей папке данных AIS\\data\\.")

    where = {}
    for folder in ("raw", "raw2"):
        d = os.path.join(ROOT, folder)
        n = 0
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    where[os.path.splitext(f)[0]] = os.path.join(d, f); n += 1
        print(f"  {folder + '/':8s} {n:4d} кадров" + ("" if n else "   — папки нет"))
    if not where:
        die("кадров не найдено вообще",
            "Проверь, что папки raw и raw2 лежат рядом со скриптом.")

    rows = list(csv.DictReader(open(labels_path, encoding="utf-8-sig")))
    lab = collections.Counter(r["label"].strip() for r in rows)
    print(f"\n  меток в CSV: {len(rows)}")
    for k, v in lab.most_common():
        mark = "→ " + COURSE3[k] if k in COURSE3 else "не идёт в обучение"
        print(f"    {k:16s} {v:4d}   {mark}")

    nomatch = [r["file"] for r in rows if r["file"].strip() not in where]
    if nomatch:
        print(f"\n  ВНИМАНИЕ: {len(nomatch)} меток без кадра, например {nomatch[:3]}")
        print("  Скорее всего кадры нарезаны заново с другими именами.")
    orphan = len(where) - (len(rows) - len(nomatch))
    if orphan > 0:
        print(f"  кадров без метки: {orphan} — они просто не попадут в датасет")

    clips = collections.Counter(n.rsplit("_t", 1)[0] for n in where)
    print(f"\n  клипов: {len(clips)} — именно по ним делится train/val")
    return rows, where, clips


# ---------------------------------------------------------------- 2
def sort_frames(rows, where, fine):
    name = "sorted_fine" if fine else "sorted_course3"
    out = os.path.join(ROOT, name)
    classes = FINE if fine else ["feeding", "alert", "empty"]
    if os.path.exists(out): shutil.rmtree(out)
    for c in classes: os.makedirs(os.path.join(out, c), exist_ok=True)

    cnt = collections.Counter()
    for r in rows:
        lab = r["label"].strip()
        cls = lab if (fine and lab in FINE) else (None if fine else COURSE3.get(lab))
        if not cls: continue
        src = where.get(r["file"].strip())
        if not src: continue
        shutil.copy2(src, os.path.join(out, cls, r["file"].strip() + ".jpg"))
        cnt[cls] += 1

    tot = sum(cnt.values())
    print(f"\n  {name}/  — всего {tot}")
    for c in classes:
        bar = "#" * round(30 * cnt[c] / max(tot, 1))
        print(f"    {c:16s} {cnt[c]:4d}  {cnt[c]/max(tot,1):5.3f}  {bar}")
    return out, cnt, tot


# ---------------------------------------------------------------- 3
def check_split():
    title(3, "ПРОВЕРКА ТВОЕЙ ФУНКЦИИ split_by_clip")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import dataset
    except Exception as e:
        die(f"не удалось загрузить dataset.py: {e}")

    import importlib
    importlib.reload(dataset)
    try:
        dataset.split_by_clip(["/tmp/a_t00000.jpg", "/tmp/b_t00000.jpg"], 0.5, 0)
    except NotImplementedError:
        die("Функция split_by_clip ещё не написана — это твоя часть работы.",
            "Открой dataset.py, найди рамку «ТВОЯ ФУНКЦИЯ» и напиши её.\n"
            "Помощник по ней:  python split_help.py   (обзор, кирпичики, подсказки,\n"
            "тесты по одному с разбором каждого падения).\n"
            "Что она должна делать — в ДО_СДАЧИ.ru.md, шаг 2, там разобрано подробно.\n"
            "Кадры при этом уже разложены, повторно этот шаг делать не надо:\n"
            "после того как напишешь, просто запусти prepare_data.py снова.")
    except Exception as e:
        die(f"функция написана, но падает: {type(e).__name__}: {e}",
            "Запусти  python dataset.py --check  — там подробные проверки.")

    try:
        dataset.check()
    except AssertionError as e:
        die(f"проверка не пройдена: {e}",
            "Смотри раздел «на чём обычно спотыкаются» в ДО_СДАЧИ.ru.md.")
    return dataset


# ---------------------------------------------------------------- 4
def build_one(dataset, sorted_dir, out_dir, classes, val_frac, seed):
    dataset.CLASSES = classes                       # набор классов на этот заход
    if os.path.exists(out_dir): shutil.rmtree(out_dir)
    stats = dataset.build(sorted_dir, out_dir, val_frac, seed)
    print(f"\n  {os.path.relpath(out_dir, ROOT)}")
    print(f"    {'класс':16s} {'train':>6s} {'val':>6s}")
    for c in classes:
        tr, va = stats.get(c, (0, 0))
        flag = "  ← в валидации пусто!" if va == 0 else ""
        print(f"    {c:16s} {tr:6d} {va:6d}{flag}")
    dataset.audit(out_dir)
    return stats


def drop_from_train(src_dir, out_dir, drop_clips, classes):
    """Копия готового датасета, из ОБУЧЕНИЯ которой убраны указанные клипы.

    Именно копия готового, а не пересборка с нуля. Если пересобирать, твоя
    split_by_clip перемешает уже другой список клипов и валидация окажется
    другой — тогда изменится сразу две вещи, и понять, что дало разницу в
    метрике, будет нельзя. Здесь валидация побитово та же, меняется только
    обучающая часть, и число отвечает ровно на вопрос про исключённый клип.
    """
    if os.path.exists(out_dir): shutil.rmtree(out_dir)
    shutil.copytree(src_dir, out_dir)
    removed, in_val = collections.Counter(), 0
    for split in ("train", "val"):
        for c in classes:
            d = os.path.join(out_dir, split, c)
            if not os.path.isdir(d): continue
            for f in sorted(os.listdir(d)):
                if f.rsplit("_t", 1)[0] not in drop_clips: continue
                if split == "val":
                    in_val += 1                      # трогать валидацию нельзя
                    continue
                os.remove(os.path.join(d, f)); removed[c] += 1
    print(f"  из обучения убрано {sum(removed.values())} кадров: "
          + " ".join(f"{c} {removed[c]}" for c in classes))
    if in_val:
        print(f"  ВНИМАНИЕ: {in_val} кадров этих клипов лежат в ВАЛИДАЦИИ и оставлены.")
        print("  Значит сравнение с прежним запуском уже не чистое — смени seed так,")
        print("  чтобы исключаемый клип целиком попал в обучение.")
    n = {s: sum(len(os.listdir(os.path.join(out_dir, s, c)))
                for c in classes if os.path.isdir(os.path.join(out_dir, s, c)))
         for s in ("train", "val")}
    print(f"  стало: train {n['train']}, val {n['val']} (валидация не тронута)")
    return out_dir


def build_fixed(sorted_dir, out_dir, classes, val_clips):
    """Датасет с ЗАРАНЕЕ НАЗВАННОЙ валидацией: клипы выбирает человек, не жребий.

    Нужно, когда вопрос звучит не «как модель работает на новом клипе», а
    «как она работает на другом виде птицы» или «на другой сцене». Случайное
    разбиение на это не отвечает: 13 клипов из 16 — синицы, и в проверку почти
    всегда попадают только они. Список клипов объявляется в команде, поэтому
    подгонки тут нет: разбиение видно целиком и не зависит от метрик.
    """
    if os.path.exists(out_dir): shutil.rmtree(out_dir)
    cnt = {"train": collections.Counter(), "val": collections.Counter()}
    seen = set()
    for c in classes:
        d = os.path.join(sorted_dir, c)
        if not os.path.isdir(d): continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith((".jpg", ".jpeg", ".png")): continue
            clip = f.rsplit("_t", 1)[0]; seen.add(clip)
            split = "val" if clip in val_clips else "train"
            t = os.path.join(out_dir, split, c); os.makedirs(t, exist_ok=True)
            shutil.copy2(os.path.join(d, f), os.path.join(t, f))
            cnt[split][c] += 1

    unknown = val_clips - seen
    if unknown:
        print(f"  ВНИМАНИЕ: таких клипов нет: {', '.join(sorted(unknown))}")
    print(f"\n  в проверке: {', '.join(sorted(val_clips & seen))}")
    print(f"  в обучении: {len(seen - val_clips)} клипов")
    print(f"\n  {os.path.relpath(out_dir, ROOT)}")
    print(f"    {'класс':16s} {'train':>6s} {'val':>6s}")
    for c in classes:
        flag = "  ← в валидации пусто!" if not cnt['val'][c] else ""
        print(f"    {c:16s} {cnt['train'][c]:6d} {cnt['val'][c]:6d}{flag}")
    ntr, nva = sum(cnt['train'].values()), sum(cnt['val'].values())
    print(f"    {'итого':16s} {ntr:6d} {nva:6d}   в валидации {nva/max(ntr+nva,1):.0%}")
    top = cnt['val'].most_common(1)
    if top:
        print(f"  константа на этой валидации: всегда «{top[0][0]}» → "
              f"accuracy {top[0][1]/max(nva,1):.3f}")
    return cnt


def build_random(sorted_dir, out_dir, n_val, seed, classes):
    """НЕЧЕСТНЫЙ датасет: деление по кадрам, а не по клипам.

    Нужен ровно для одного — показать числом, насколько завышаются метрики при
    случайном делении. Обучать на нём что-то всерьёз нельзя: кадры одного клипа
    попадают и в train, и в val, модель проверяется на том, что видела.
    """
    files = []
    for c in classes:
        d = os.path.join(sorted_dir, c)
        if not os.path.isdir(d): continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                files.append((os.path.join(d, f), c))
    random.Random(seed).shuffle(files)
    if os.path.exists(out_dir): shutil.rmtree(out_dir)
    cnt = {"train": collections.Counter(), "val": collections.Counter()}
    for i, (src, c) in enumerate(files):
        split = "val" if i < n_val else "train"
        dst = os.path.join(out_dir, split, c)
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(src, os.path.join(dst, os.path.basename(src)))
        cnt[split][c] += 1

    both = set()
    for c in classes:
        tr = {f.rsplit("_t", 1)[0] for f in os.listdir(os.path.join(out_dir, "train", c))}
        va = {f.rsplit("_t", 1)[0] for f in os.listdir(os.path.join(out_dir, "val", c))}
        both |= tr & va
    print(f"\n  {os.path.relpath(out_dir, ROOT)}   (деление по кадрам)")
    print(f"    {'класс':16s} {'train':>6s} {'val':>6s}")
    for c in classes:
        print(f"    {c:16s} {cnt['train'][c]:6d} {cnt['val'][c]:6d}")
    print(f"    клипов, попавших в ОБЕ выборки: {len(both)}  — так и задумано")
    return cnt


def split_by_episode(files, ep_sec, val_frac, seed, guard_sec):
    """Деление по ЭПИЗОДАМ: клип режется на куски по ep_sec секунд.

    Идея Кати. Единица независимости — не весь клип, а эпизод: за несколько
    секунд план успевает смениться, а птица — сменить поведение пару раз.
    Число, которое из этого получится, означает «обобщение на другой момент той
    же съёмки», а не «на новую съёмку». Это законная промежуточная ступень
    шкалы кадр -> эпизод -> клип, и она ближе к настоящей задаче помощника по
    разметке, чем любая из крайностей.

    Защитная полоса. Соседние эпизоды стыкуются, и кадр на самой границе всё
    ещё почти дубликат кадра по ту сторону. Поэтому из валидации выбрасываются
    все кадры, у которых в обучении есть сосед ближе guard_sec секунд ПО ТОМУ ЖЕ
    КЛИПУ. Проверяется не «первые и последние N кадров эпизода», а именно
    расстояние до ближайшего обучающего кадра — так закрываются и стыки, и
    случай, когда в валидацию попали два эпизода подряд.

    Имена кадров пронумерованы в десятых долях секунды (шаг 5 = 0.5 c).
    """
    def key(p):
        stem = os.path.splitext(os.path.basename(p))[0]
        clip, t = stem.rsplit("_t", 1)
        return clip, int(t) / 10.0                       # секунды

    units = collections.defaultdict(list)
    for f in files:
        clip, sec = key(f)
        units[(clip, int(sec // ep_sec))].append(f)

    names = sorted(units)
    random.Random(seed).shuffle(names)
    k = max(1, min(round(val_frac * len(names)), len(names) - 1))
    va_units, tr_units = names[:k], names[k:]

    train = [f for u in tr_units for f in units[u]]
    val_raw = [f for u in va_units for f in units[u]]

    # секунды обучающих кадров по клипам — для проверки защитной полосы
    tr_sec = collections.defaultdict(list)
    for f in train:
        clip, sec = key(f); tr_sec[clip].append(sec)

    val, dropped = [], 0
    for f in val_raw:
        clip, sec = key(f)
        if any(abs(sec - s) <= guard_sec for s in tr_sec.get(clip, ())):
            dropped += 1
        else:
            val.append(f)
    return train, val, {"episodes": len(names), "val_episodes": k,
                        "val_before": len(val_raw), "dropped": dropped}


def build_episode(sorted_dir, out_dir, classes, ep_sec, val_frac, seed,
                  guard_sec, drop_clips):
    all_files, cls_of = [], {}
    for c in classes:
        d = os.path.join(sorted_dir, c)
        if not os.path.isdir(d): continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith((".jpg", ".jpeg", ".png")): continue
            if f.rsplit("_t", 1)[0] in drop_clips: continue
            p = os.path.join(d, f); all_files.append(p); cls_of[p] = c

    tr, va, st = split_by_episode(all_files, ep_sec, val_frac, seed, guard_sec)
    if os.path.exists(out_dir): shutil.rmtree(out_dir)
    cnt = {"train": collections.Counter(), "val": collections.Counter()}
    for split, group in (("train", tr), ("val", va)):
        for f in group:
            d = os.path.join(out_dir, split, cls_of[f])
            os.makedirs(d, exist_ok=True)
            shutil.copy2(f, os.path.join(d, os.path.basename(f)))
            cnt[split][cls_of[f]] += 1

    print(f"\n  эпизодов по {ep_sec:g} c: {st['episodes']}, "
          f"в валидацию ушло {st['val_episodes']}")
    print(f"  защитная полоса {guard_sec:g} c выбросила из валидации "
          f"{st['dropped']} кадров из {st['val_before']}")
    if drop_clips:
        print(f"  исключены целиком: {', '.join(sorted(drop_clips))}")
    print(f"\n  {os.path.relpath(out_dir, ROOT)}")
    print(f"    {'класс':16s} {'train':>6s} {'val':>6s}")
    for c in classes:
        flag = "  ← в валидации пусто!" if not cnt['val'][c] else ""
        print(f"    {c:16s} {cnt['train'][c]:6d} {cnt['val'][c]:6d}{flag}")
    nva = sum(cnt['val'].values()); ntr = sum(cnt['train'].values())
    print(f"    {'итого':16s} {ntr:6d} {nva:6d}   в валидации {nva/max(ntr+nva,1):.0%}")
    top = cnt['val'].most_common(1)
    if top:
        print(f"  константа на этой валидации: всегда «{top[0][0]}» → "
              f"accuracy {top[0][1]/max(nva,1):.3f}")
    return cnt


def val_clips(out_dir, classes):
    s = set()
    for c in classes:
        d = os.path.join(out_dir, "val", c)
        if os.path.isdir(d):
            for f in os.listdir(d):
                s.add(f.rsplit("_t", 1)[0])
    return sorted(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="labels_all.csv")
    ap.add_argument("--val-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only-sort", action="store_true")
    ap.add_argument("--random-split", action="store_true",
                    help="собрать ещё и датасет со случайным делением ПО КАДРАМ")
    ap.add_argument("--episodes", type=float, default=0,
                    help="собрать датасет с делением ПО ЭПИЗОДАМ, длина эпизода в секундах")
    ap.add_argument("--guard", type=float, default=2.0,
                    help="защитная полоса вокруг обучающих кадров, секунд")
    ap.add_argument("--drop-clips", default="",
                    help="клипы, которые не брать вообще, через запятую")
    ap.add_argument("--val-clips", default="",
                    help="назвать валидационные клипы явно, через запятую")
    a = ap.parse_args()
    drop_clips = {s.strip() for s in a.drop_clips.split(",") if s.strip()}
    fixed_val = {s.strip() for s in a.val_clips.split(",") if s.strip()}

    log = os.path.join(ROOT, "log_podgotovka.txt")
    try: sys.stdout = Tee(log)
    except Exception: pass
    print(f"команда: python prepare_data.py " + " ".join(sys.argv[1:]))

    rows, where, clips = inventory(os.path.join(ROOT, a.labels))

    title(2, "РАСКЛАДКА КАДРОВ ПО КЛАССАМ")
    print("  обе схемы сразу: три зачётных класса и шесть мелких")
    s3, cnt3, tot3 = sort_frames(rows, where, fine=False)
    s6, cnt6, tot6 = sort_frames(rows, where, fine=True)
    if tot3 != tot6:
        print(f"\n  СТРАННО: в схемах разное число кадров ({tot3} и {tot6}).")
        print("  Должно совпадать — обе строятся из одних и тех же меток.")
    else:
        print(f"\n  в обеих схемах {tot3} кадров — сравнение будет контролируемым")

    base_cls, base_n = cnt3.most_common(1)[0]
    print(f"\n  базовое решение (всегда «{base_cls}»): accuracy {base_n/tot3:.3f}")
    print("  модель обязана быть выше этого числа, иначе она ничего не выучила")

    if a.only_sort:
        print("\nостановка после раскладки (--only-sort)")
        return

    dataset = check_split()
    print("  функция написана и все проверки пройдены")

    title(4, "СБОРКА ДАТАСЕТОВ")
    d3 = os.path.join(ROOT, "datasets", "birds_v1_course3")
    d6 = os.path.join(ROOT, "datasets", "birds_v1_fine")
    build_one(dataset, s3, d3, ["feeding", "alert", "empty"], a.val_frac, a.seed)
    build_one(dataset, s6, d6, FINE, a.val_frac, a.seed)

    title(5, "ЧТО ПОЛУЧИЛОСЬ")
    vc = val_clips(d3, ["feeding", "alert", "empty"])
    print(f"  клипов в валидации: {len(vc)} из {len(clips)}")
    for c in vc: print(f"    {c}  ({clips[c]} кадров)")

    # val_frac задаёт долю КЛИПОВ, а клипы у нас от 11 до 164 кадров.
    # Поэтому доля кадров может оказаться совсем другой, и это надо видеть.
    ntr = sum(len(os.listdir(os.path.join(d3, "train", c)))
              for c in ("feeding", "alert", "empty"))
    nva = sum(len(os.listdir(os.path.join(d3, "val", c)))
              for c in ("feeding", "alert", "empty"))
    frac = nva / max(ntr + nva, 1)
    print(f"\n  кадров: train {ntr}, val {nva} — в валидации {frac:.0%}")
    if not 0.15 <= frac <= 0.40:
        print(f"  ВНИМАНИЕ: просили {a.val_frac:.0%} клипов, но по кадрам вышло {frac:.0%}.")
        print("  Клипы у нас от 11 до 164 кадров, так что доля кадров гуляет.")
        print("  Если перекос мешает — попробуй другой seed:")
        print("    python prepare_data.py --seed 1     (потом 2, 3 — пока не устроит)")
        print("  Менять seed до обучения нормально; после — уже нет, это подгонка.")
    else:
        print("  доля разумная, менять ничего не надо")
    print("\n  ЭТИ КЛИПЫ МОДЕЛЬ НЕ УВИДИТ. Один из них бери для демо с камерой —")
    print("  тогда демонстрация будет ещё и честной проверкой.")
    print("\n  Сравнить несколько зёрен и выбрать разбиение, где все три класса в")
    print("  валидации представлены прилично:  python split_help.py --result --seeds 10")

    if fixed_val:
        extra("валидация из названных клипов")
        print("  Клипы для проверки выбраны вручную, а не жребием. Это отвечает на")
        print("  вопрос «как модель работает на другой сцене или другом виде», на")
        print("  который случайное разбиение ответить не может: 13 клипов из 16 —")
        print("  синицы, и в проверку почти всегда попадают только они.")
        df = os.path.join(ROOT, "datasets", "birds_v1_fixval")
        build_fixed(s3, df, ["feeding", "alert", "empty"], fixed_val)
        print(f"""
  Обучить:

      python train.py --exp frozen --aug off --data datasets\\birds_v1_fixval --tag fixval

  Сравнивать с frozen_augoff можно только по выигрышу над СВОЕЙ константой:
  состав классов в этой проверке другой.""")

    if drop_clips:
        extra("клиповое деление без исключённых клипов")
        print("  Та же единица деления и та же валидация, что у зачётных запусков.")
        print("  Меняется ровно одно: исключённые клипы уходят из обучения.")
        dd = os.path.join(ROOT, "datasets", "birds_v1_course3_drop")
        drop_from_train(d3, dd, drop_clips, ["feeding", "alert", "empty"])
        print(f"""
  Обучить и сравнить с frozen_augoff (accuracy 0.402, macro-F1 0.356):

      python train.py --exp frozen --aug off --data datasets\\birds_v1_course3_drop --tag drop""")

    if a.episodes:
        extra("деление по эпизодам")
        print("""  Средняя ступень шкалы: кадр -> эпизод -> клип. Единица не весь клип, а
  кусок в несколько секунд — за это время план успевает смениться, а птица
  сменить поведение. Кадры валидации, у которых в обучении есть сосед ближе
  защитной полосы, выбрасываются, чтобы не сравнивать почти-дубликаты.

  Число отсюда означает «обобщение на другой момент той же съёмки» —
  это режим помощника по разметке, а не работа на новой записи.""")
        suffix = "_noryab" if drop_clips else ""
        de = os.path.join(ROOT, "datasets", "birds_v1_episode" + suffix)
        build_episode(s3, de, ["feeding", "alert", "empty"], a.episodes,
                      a.val_frac, a.seed, a.guard, drop_clips)
        print(f"""
  Обучить в той же конфигурации, что и лучший честный запуск:

      python train.py --exp frozen --aug off --data {os.path.relpath(de, ROOT)} --tag ep{int(a.episodes)}{suffix}

  Сравнивать с frozen_augoff (accuracy 0.402, macro-F1 0.356) — там всё то же
  самое, кроме единицы деления.""")

    if a.random_split:
        extra("деление по кадрам, для сравнения")
        print("  Те же 792 кадра, но поделённые случайно по кадрам, а не по клипам.")
        print("  Число кадров в валидации то же, что у честного, — чтобы сравнение")
        print("  отличалось ровно одним: способом деления.")
        build_random(s3, os.path.join(ROOT, "datasets", "birds_v1_random"),
                     nva, a.seed, ["feeding", "alert", "empty"])
        print("""
  Обучить на нём и сравнить с честным запуском:

      python train.py --exp small --frac 1.0 --data datasets\\birds_v1_random --tag random

  Разница между двумя accuracy — это и есть цена псевдорепликации, измеренная
  на своих данных. Модель на нечестном датасете не годится ни для чего, кроме
  этой одной строчки в отчёте.""")

    print("\n  дальше:")
    print("    python train.py --exp small --frac 0.33      зачётный эксперимент 1")
    print("    python train.py --exp aug --aug strong       зачётный эксперимент 2")
    print("    python train.py --exp frozen                 зачётный эксперимент 3")
    print("    python train.py --exp base --data datasets\\birds_v1_fine   цена детализации")
    print("\n  всё готово.")
    print(f"\n  весь этот вывод сохранён в log_podgotovka.txt — окно можно закрывать")


if __name__ == "__main__":
    main()
