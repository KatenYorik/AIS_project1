# -*- coding: utf-8 -*-
"""Вырезки птиц из WetlandBirds БЕЗ скачивания всех 9.4 ГБ.

    pip install remotezip opencv-python
    python wb_stream.py --root ..\\wetlandbirds --out datasets\\pretrain

Зачем. Полный архив видео весит 9.4 ГБ. Но zip хранит оглавление отдельно от
данных, а Zenodo отдаёт куски файла по запросу (HTTP Range). Значит можно прочитать
оглавление и качать РОВНО ТЕ видео, которые нужны, по одному: скачали → вырезали
птиц по аннотациям → удалили. На диске в каждый момент одно видео.

Формат аннотаций (проверено на файле, а не угадано):

    разделитель  ;
    колонки      species_id ; species ; video_name ; frame ; bounding_boxes
    bounding_boxes = [(x1, y1, x2, y2, поведение, номер особи), ...]

Метка для предобучения — ВИД птицы, а не поведение. Причина: справочник
behaviors_ID.csv перечисляет семь поведений (0–6), а в данных встречается восемь
значений (0–7), то есть соответствие id и названий не совпадает с публикацией.
Виды же заданы прямо в колонке `species` и сомнений не вызывают. Для предобучения
это и нужно: задача этапа 1 — научить сеть признакам «птица в кадре», а не нашим
трём классам поведения, которые появятся на этапе 2.

    --by behaviour   если всё же нужны поведения; тогда берётся наша
                     реконструкция карты, и в отчёте это надо называть реконструкцией
    --videos DIR     видео уже скачаны — работать с диска, сеть не нужна
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

import argparse, ast, collections, csv, os, random, re, shutil, tempfile

ZIP_URL = "https://zenodo.org/records/15696105/files/videos.zip"

# Реконструкция карты поведений по геометрии рамок (см. ИТОГИ_ВСЕ.ru.md).
# Используется только при --by behaviour и только как реконструкция.
BEHAV = {0: "feeding", 5: "alert"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="папка с bounding_boxes.csv")
    ap.add_argument("--out", default="datasets/pretrain")
    ap.add_argument("--by", choices=["species", "behaviour"], default="species")
    ap.add_argument("--per-class", type=int, default=150)
    ap.add_argument("--per-video", type=int, default=40)
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--pad", type=float, default=0.15)
    ap.add_argument("--url", default=ZIP_URL)
    ap.add_argument("--videos", default="",
                    help="папка с уже скачанными видео — тогда сеть не нужна вовсе")
    ap.add_argument("--retries", type=int, default=5,
                    help="повторы при обрыве соединения")
    ap.add_argument("--limit-gb", type=float, default=3.0)
    ap.add_argument("--plan-only", action="store_true",
                    help="показать план и выйти, ничего не качая")
    a = ap.parse_args()

    path = os.path.join(a.root, "bounding_boxes.csv")
    if not os.path.exists(path): sys.exit(f"не найден {path}")

    # ---------------------------------------------------------------- разбор
    by_video, classes = collections.defaultdict(list), collections.Counter()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            try:
                boxes = ast.literal_eval(r["bounding_boxes"])
                fr = int(float(r["frame"]))
            except Exception:
                continue
            for b in boxes:
                if len(b) < 6: continue
                cls = (slug(r["species"]) if a.by == "species"
                       else BEHAV.get(int(b[4])))
                if not cls: continue
                by_video[r["video_name"]].append((fr, [int(float(v)) for v in b[:4]], cls))
                classes[cls] += 1

    print(f"видео: {len(by_video)}, классов ({a.by}): {len(classes)}")
    for c, n in classes.most_common():
        print(f"  {c:24s} {n:7d} рамок")

    # ---------------------------------------------------------------- план
    # какие видео брать: по очереди, пока каждый класс не наберёт свою норму
    rng = random.Random(0)
    videos = sorted(by_video); rng.shuffle(videos)
    plan, need = [], collections.Counter()
    for vid in videos:
        cs = collections.Counter(c for _, _, c in by_video[vid])
        if all(need[c] >= a.per_class for c in cs): continue
        plan.append(vid)
        for c in cs: need[c] += min(a.per_video, cs[c])
        if all(need[c] >= a.per_class for c in classes): break
    print(f"\nпонадобится видео: {len(plan)} из {len(by_video)}")
    print(f"ожидаемая загрузка: примерно {len(plan) * 0.05:.1f} ГБ "
          f"(в среднем ~50 МБ на видео)")
    if a.plan_only:
        print("\n--plan-only: ничего не скачано")
        return

    try:
        import cv2
    except ImportError:
        sys.exit("нужен opencv:  pip install opencv-python")

    for c in classes: os.makedirs(os.path.join(a.out, c), exist_ok=True)

    zf, entries = None, {}
    if a.videos:
        # Локальный режим: видео уже скачаны, сеть не нужна.
        for dirpath, _, files in os.walk(a.videos):
            for n in files:
                if n.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                    entries[os.path.splitext(n)[0].lower()] = os.path.join(dirpath, n)
        print(f"\nвидеофайлов в папке {a.videos}: {len(entries)}")
        if not entries: sys.exit("в этой папке видео не нашлось")
    else:
        try:
            from remotezip import RemoteZip
        except ImportError:
            sys.exit("нужен remotezip:  pip install remotezip")
        print("\nчитаю оглавление архива по сети (сам архив не качается) …")
        # Соединение может рваться на рукопожатии TLS — это лечится повтором.
        for attempt in range(1, a.retries + 1):
            try:
                zf = RemoteZip(a.url); break
            except Exception as e:
                print(f"  попытка {attempt}/{a.retries}: {type(e).__name__}")
                if attempt == a.retries:
                    sys.exit("оглавление прочитать не вышло. Скачай архив целиком:\n"
                             "  curl.exe -L -C - --retry 20 --retry-all-errors "
                             "-o videos.zip \"" + ZIP_URL + "\"\n"
                             "  tar -xf videos.zip\n"
                             "и запусти снова с  --videos <папка с видео>")
        for n in zf.namelist():
            if n.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                entries[os.path.splitext(os.path.basename(n))[0].lower()] = n
        print(f"видеофайлов в архиве: {len(entries)}")
    miss = [v for v in plan if v.lower() not in entries]
    if miss:
        print(f"  нет в архиве: {len(miss)}, например {miss[:3]}")

    saved, got, used = collections.Counter(), 0, 0
    tmp = tempfile.mkdtemp(prefix="wb_")
    try:
        for vid in plan:
            if all(saved[c] >= a.per_class for c in classes):
                print("\nнабрали по всем классам"); break
            if got / 1e9 >= a.limit_gb:
                print(f"\nдостигнут предел {a.limit_gb} ГБ"); break
            name = entries.get(vid.lower())
            if name is None: continue

            if zf is None:
                f, local = name, True                  # видео уже на диске
            else:
                f, local = os.path.join(tmp, os.path.basename(name)), False
                for attempt in range(1, a.retries + 1):
                    try:
                        with zf.open(name) as src, open(f, "wb") as dst:
                            shutil.copyfileobj(src, dst, 1 << 20)
                        break
                    except Exception as e:
                        if attempt == a.retries:
                            print(f"  {vid}: не скачалось ({type(e).__name__})"); f = None
                if f is None: continue
                got += os.path.getsize(f)
            used += 1

            cap = cv2.VideoCapture(f)
            if cap.isOpened():
                items = by_video[vid][:]; rng.shuffle(items)
                took = collections.Counter()
                for fr, box, cls in items:
                    if saved[cls] >= a.per_class: continue
                    if sum(took.values()) >= a.per_video: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
                    ok, img = cap.read()
                    if not ok: continue
                    h, w = img.shape[:2]
                    x1, y1, x2, y2 = box
                    dx, dy = int((x2 - x1) * a.pad), int((y2 - y1) * a.pad)
                    x1, y1 = max(0, x1 - dx), max(0, y1 - dy)
                    x2, y2 = min(w, x2 + dx), min(h, y2 + dy)
                    if x2 - x1 < 20 or y2 - y1 < 20: continue
                    crop = cv2.resize(img[y1:y2, x1:x2], (a.size, a.size))
                    # Имя строго в формате проекта <источник>_t<номер>: тогда
                    # split_by_clip увидит видео как «клип» и разложит выборки по
                    # видео, а не по кадрам — та же защита, что на своей съёмке.
                    cv2.imwrite(os.path.join(a.out, cls, f"{slug(vid)}_t{fr:06d}.jpg"),
                                crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    saved[cls] += 1; took[cls] += 1
                cap.release()
            if not local: os.remove(f)             # своё видео не трогаем
            print(f"  [{used:3d}/{len(plan)}] {vid:26s} {got/1e9:5.2f} ГБ   "
                  f"вырезок {sum(saved.values())}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if zf is not None:
            try: zf.close()
            except Exception: pass

    print("\nитог:")
    for c in sorted(saved): print(f"  {c:24s} {saved[c]:5d}")
    print(f"\nвсего {sum(saved.values())} вырезок в {a.out}")
    print(f"скачано {got/1e9:.2f} ГБ, видео на диске не осталось")
    print("\nдальше:")
    print(f"  python dataset.py --sorted {a.out} --out datasets\\pretrain_split "
          f"--val-frac 0.2 --classes auto")
    print("  python train.py --exp pretrain --stage 1 --pretrain-data datasets\\pretrain_split")
    print("  python train.py --exp pretrain --stage 2")


if __name__ == "__main__":
    main()
