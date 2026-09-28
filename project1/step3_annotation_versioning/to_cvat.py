# -*- coding: utf-8 -*-
"""Готовит нашу разметку к импорту в CVAT и Roboflow. Переразмечать ничего не надо.

    python to_cvat.py --labels labels_all.csv --raw raw --raw2 raw2 --out cvat

Что делает и зачем именно так.

Требование курса — «разметка в CVAT/Roboflow, формат YOLO». Оно про инструмент и
формат, а не про то, какой мышкой щёлкали. Разметка уже сделана в своём инструменте
(иначе три прохода по 946 кадров с протягиванием метки заняли бы не полтора часа, а
день), поэтому правильный ход — не переразмечать, а ИМПОРТИРОВАТЬ готовое.

На выходе три вещи:

  annotations_cvat.xml   аннотации в формате CVAT for images 1.1 — теги на каждый
                         кадр плюс атрибуты side / fixation / count. Загружается в
                         задачу, созданную из тех же папок, одним действием.
  labels_cvat.json       описание меток и атрибутов — вставляется в задачу при
                         создании (вкладка Raw в списке меток).
  roboflow/<класс>/*.jpg три зачётных класса папками. Roboflow принимает такую
                         структуру для классификации напрямую, без разметки вручную.
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

import argparse, csv, json, os, shutil, xml.sax.saxutils as sx

COURSE3 = {"head_down": "feeding", "handling": "feeding",
           "head_up_ahead": "alert", "head_up_turnL": "alert",
           "head_up_turnR": "alert", "no_bird": "empty"}

# цвета произвольные, CVAT требует их в описании меток
COLORS = {"head_down": "#e0b341", "handling": "#d98f3c", "head_up_ahead": "#4a90d9",
          "head_up_turnL": "#6fa8dc", "head_up_turnR": "#3b6ea5",
          "transit": "#8e7cc3", "no_bird": "#666666", "ambiguous": "#b04a4a"}


def size_of(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="labels_all.csv")
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--raw2", default="raw2")
    ap.add_argument("--out", default="cvat")
    ap.add_argument("--no-copy", action="store_true", help="не собирать roboflow/")
    ap.add_argument("--labels-mode", choices=["fine", "course3"], default="fine",
                    help="какие метки писать в XML: 8 мелких или 3 зачётных")
    ap.add_argument("--zip", action="store_true", help="собрать images.zip для загрузки")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.labels, encoding="utf-8-sig")))
    os.makedirs(a.out, exist_ok=True)

    # где лежит каждый кадр
    where = {}
    for folder in (a.raw, a.raw2):
        if not os.path.isdir(folder): continue
        for f in os.listdir(folder):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                where[os.path.splitext(f)[0]] = os.path.join(folder, f)
    missing = [r["file"] for r in rows if r["file"] not in where]
    if missing:
        print(f"ВНИМАНИЕ: не найдено {len(missing)} кадров, например {missing[:3]}")

    # какую метку писать в XML
    def tag_of(lab):
        return COURSE3.get(lab) if a.labels_mode == "course3" else lab

    # ---------------------------------------------------------------- метки для CVAT
    labels = []
    for name in sorted({tag_of(r["label"]) for r in rows if tag_of(r["label"])}):
        labels.append({
            "name": name, "color": COLORS.get(name, "#999999"), "type": "tag",
            "attributes": [
                {"name": "side", "input_type": "select", "mutable": False,
                 "values": ["none", "L", "R", "F", "A"], "default_value": "none"},
                {"name": "fixation", "input_type": "select", "mutable": False,
                 "values": ["none", "yes", "no", "unk"], "default_value": "none"},
                {"name": "count", "input_type": "text", "mutable": False,
                 "values": [], "default_value": ""},   # текстовый атрибут
            ],
        })
    with open(os.path.join(a.out, "labels_cvat.json"), "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=1)

    # ---------------------------------------------------------------- аннотации
    xml = ['<?xml version="1.0" encoding="utf-8"?>', "<annotations>",
           "  <version>1.1</version>"]
    n = 0
    for i, r in enumerate(rows):
        name = r["file"]
        tag = tag_of(r["label"])
        if name not in where or not tag: continue
        path = where[name]
        try: w, h = size_of(path)
        except Exception: w, h = 0, 0
        fn = os.path.basename(path)
        xml.append(f'  <image id="{i}" name="{sx.escape(fn)}" width="{w}" height="{h}">')
        xml.append(f'    <tag label="{sx.escape(tag)}" source="manual">')
        for k in ("side", "fixation", "count"):
            v = (r.get(k) or "").strip()
            if v:
                xml.append(f'      <attribute name="{k}">{sx.escape(v)}</attribute>')
        xml.append("    </tag>")
        xml.append("  </image>")
        n += 1
    xml.append("</annotations>")
    with open(os.path.join(a.out, "annotations_cvat.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(xml))
    print(f"annotations_cvat.xml: {n} кадров с тегами, метки — {a.labels_mode}")

    # ---------------------------------------------------------------- архив кадров
    if a.zip:
        import zipfile
        zp = os.path.join(a.out, "images.zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:   # jpg уже сжат
            for r in rows:
                if r["file"] in where:
                    z.write(where[r["file"]], os.path.basename(where[r["file"]]))
        print(f"images.zip: {os.path.getsize(zp)/1e6:.0f} МБ — грузится в CVAT одним файлом")

    # ---------------------------------------------------------------- Roboflow
    if not a.no_copy:
        root = os.path.join(a.out, "roboflow")
        if os.path.exists(root): shutil.rmtree(root)
        cnt = {}
        for r in rows:
            cls = COURSE3.get(r["label"])
            if not cls or r["file"] not in where: continue
            d = os.path.join(root, cls)
            os.makedirs(d, exist_ok=True)
            shutil.copy2(where[r["file"]], os.path.join(d, r["file"] + ".jpg"))
            cnt[cls] = cnt.get(cls, 0) + 1
        print("roboflow/:", cnt, "— папка на класс, загружается как есть")

    print(f"\nготово в {a.out}/")
    print("дальше — README_CVAT.ru.md, там по шагам")


if __name__ == "__main__":
    main()
