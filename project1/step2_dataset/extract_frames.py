"""
Шаг 1: видео → кадры с именами, в которых зашиты клип и время.

Имя кадра — это не мелочь оформления, а несущая конструкция всего проекта:

    clip03_t00142.jpg
    ^^^^^^ ^^^^^^
    клип   время в кадрах от начала клипа (при fps=1 это просто секунды)

Из этого имени потом восстанавливаются две вещи, которые иначе теряются навсегда:
    1) порядок кадров внутри клипа — без него невозможен марковский анализ;
    2) принадлежность клипу — без неё нельзя честно разбить train/val
       (кадры одного клипа почти дубликаты, см. dataset.py).

Поэтому переименовывать кадры после извлечения нельзя. Раскладывать по папкам —
можно и нужно, имя при этом сохраняется.

Использование:
    python src/extract_frames.py --videos "D:/birds/*.mp4" --out frames --fps 1

Дальше кадры раскладываются руками по папкам feeding / alert / empty / ambiguous.
"""
from __future__ import annotations

import sys as _sys, pathlib as _pl  # общие пути AIS, см. common/aispaths.py
_sys.path.insert(0, str(next(_p / "common" for _p in _pl.Path(__file__).resolve().parents
                            if (_p / "common" / "aispaths.py").is_file())))
import aispaths
aispaths.to_data()  # данные, runs, results и пути в аргументах — от AIS/data
import argparse
import csv
import glob
import os
import re
import shutil
import subprocess
import sys


def clip_id(video_path: str, index: int) -> str:
    """Короткий устойчивый идентификатор клипа.

    Берётся имя файла без расширения, чистится до латиницы и цифр. Если после
    чистки ничего не осталось (например, имя было кириллицей), подставляется
    порядковый номер. Главное требование — идентификатор не должен содержать
    символ подчёркивания, иначе разбор имени кадра станет неоднозначным.
    """
    stem = os.path.splitext(os.path.basename(video_path))[0]
    clean = re.sub(r"[^A-Za-z0-9]+", "", stem)
    # Требуем, чтобы идентификатор начинался с буквы: чисто цифровое имя
    # («12» от «Синицы 12 мая») ничего не говорит и легко совпадёт с другим.
    if not clean or not clean[0].isalpha():
        return f"clip{index:02d}"
    return clean


def parse_frame_name(filename: str) -> tuple[str, float]:
    """Обратная операция: имя кадра → (идентификатор клипа, время в секундах).

    Это функция, которой пользуется весь остальной проект, поэтому она вынесена
    сюда и покрыта самопроверкой внизу файла.
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    # Два разделителя, а не один. `_t` — своя съёмка, номер это время в
    # десятых долях секунды. `_f` — вырезки из чужих видео (WetlandBirds),
    # номер это индекс кадра. Для разбора важно только то, что слева от
    # разделителя стоит идентификатор источника: по нему делятся выборки.
    m = re.match(r"^(.+)_[tf](\d+)$", stem)
    if not m:
        raise ValueError(
            f"имя кадра не по формату <источник>_t<номер> или _f<номер>: {filename}")
    return m.group(1), float(m.group(2))


def extract(video: str, out_dir: str, cid: str, fps: float) -> int:
    """Вызвать ffmpeg и вернуть число извлечённых кадров.

    -vf fps=N        оставить N кадров в секунду (1 более чем достаточно:
                     соседние кадры видео почти неотличимы и обучению не помогают)
    -q:v 2           качество JPEG: 2 — почти без потерь, 31 — мусор
    -start_number 0  чтобы время начиналось с нуля, а не с единицы
    """
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, f"{cid}_t%05d.jpg")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-i", video, "-vf", f"fps={fps}", "-q:v", "2",
           "-start_number", "0", pattern]
    subprocess.run(cmd, check=True)
    return len(glob.glob(os.path.join(out_dir, f"{cid}_t*.jpg")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True,
                    help='маска файлов, например "D:/birds/*.mp4" (кавычки обязательны)')
    ap.add_argument("--out", default="frames", help="куда складывать кадры")
    ap.add_argument("--fps", type=float, default=1.0,
                    help="кадров в секунду; 1 — разумное значение по умолчанию")
    ap.add_argument("--classes", default="feeding,alert,empty,ambiguous",
                    help="папки, которые создать для ручной раскладки")
    a = ap.parse_args()

    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg не найден. Установить: https://ffmpeg.org/download.html "
                 "и добавить в PATH.")

    videos = sorted(glob.glob(a.videos))
    if not videos:
        sys.exit(f"по маске {a.videos} не найдено ни одного файла")

    # Папки для ручной раскладки создаются заранее, чтобы не отвлекаться потом.
    for c in a.classes.split(","):
        os.makedirs(os.path.join(a.out, "sorted", c.strip()), exist_ok=True)

    raw = os.path.join(a.out, "raw")
    rows, total = [], 0
    seen: set[str] = set()
    for i, v in enumerate(videos):
        cid = clip_id(v, i)
        # Защита от совпадения идентификаторов у файлов из разных папок.
        while cid in seen:
            cid += "x"
        seen.add(cid)

        n = extract(v, raw, cid, a.fps)
        total += n
        rows.append({"clip_id": cid, "video": v, "frames": n,
                     # Поля ниже заполняются вручную — их знает только человек.
                     "date": "", "time_of_day": "", "weather": "", "feeder": "",
                     "notes": ""})
        print(f"{cid:12s} {n:5d} кадров  ←  {os.path.basename(v)}")

    # Таблица метаданных: пять минут работы сейчас, невосстановимо потом.
    meta_path = os.path.join(a.out, "clips.csv")
    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"\nВсего кадров: {total}")
    print(f"Кадры:        {raw}")
    print(f"Папки для раскладки: {os.path.join(a.out, 'sorted')}")
    print(f"Метаданные:   {meta_path}  ← заполнить руками колонки date/weather/feeder")


# ---------------------------------------------------------------- самопроверка
if __name__ == "__main__" and "--videos" not in sys.argv:
    # Проверяем разбор имён — это то, на чём держатся последовательности.
    assert parse_frame_name("clip03_t00142.jpg") == ("clip03", 142.0)
    assert parse_frame_name("frames/sorted/alert/tits2024_t00007.jpg") == ("tits2024", 7.0)
    # вырезки из чужих видео: тот же разбор, другой разделитель
    assert parse_frame_name("013_black_headed_gull_f000110.jpg") == ("013_black_headed_gull", 110.0)
    assert clip_id("D:/birds/Синицы 12 мая.mp4", 4) == "clip04"      # кириллица → номер
    assert clip_id("D:/birds/tits_feeder-2.MP4", 0) == "titsfeeder2"
    for bad in ("noprefix.jpg", "clip03.jpg", "clip03_t.jpg"):
        try:
            parse_frame_name(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"не поймано битое имя: {bad}")
    print("extract_frames.py: разбор имён работает")
    print("Запуск: python src/extract_frames.py --videos \"D:/birds/*.mp4\" --out frames")
elif __name__ == "__main__":
    main()
