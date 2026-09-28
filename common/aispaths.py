# -*- coding: utf-8 -*-
"""Общие пути проекта. Один источник правды о том, где лежат данные.

Раньше все скрипты жили в razmetka\ и искали данные относительно текущей папки:
data\, runs\, results\, labels_all.csv. После раскладки по шагам скрипты лежат
в разных папках, а данные — в одной общей AIS\data\.

Чтобы все прежние команды работали без изменений аргументов, скрипт, который
читает или пишет данные, в начале переходит в AIS\data\:

    import sys, pathlib
    sys.path.insert(0, str(next(p / "common" for p in pathlib.Path(__file__).resolve().parents
                                if (p / "common" / "aispaths.py").is_file())))
    import aispaths
    aispaths.to_data()

После этого пути вида  runs\classify\pretrain_stage2\weights\best.pt,
datasets\birds_v1_course3, results\*.json, labels_all.csv  значат ровно то же,
что раньше значили внутри razmetka\ (кроме data\ → datasets\).

ВАЖНО: пути в аргументах командной строки тоже считаются от AIS\data\, а не от
папки, из которой запущен скрипт. Абсолютные пути работают как обычно.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # AIS\
DATA = ROOT / "data"                                # общие данные
DATASETS = DATA / "datasets"                        # собранные датасеты YOLO
RUNS = DATA / "runs"                                # веса ultralytics
RESULTS = DATA / "results"                          # метрики *.json
LABELS = DATA / "labels_all.csv"                    # главный файл разметки
FINAL_PT = RUNS / "classify" / "pretrain_stage2" / "weights" / "best.pt"
FINAL_ONNX = FINAL_PT.with_suffix(".onnx")
ROS_PKG = ROOT / "project2" / "ros2_ws" / "src" / "birdcls" / "birdcls"   # efe.py и узлы
WETLANDBIRDS = ROOT / "wetlandbirds"
VIDEOS = ROOT / "птицы"


def to_data() -> Path:
    """Перейти в AIS\\data\\. Возвращает прежнюю текущую папку."""
    prev = Path.cwd()
    if not DATA.is_dir():
        sys.exit(f"нет папки с данными: {DATA}")
    os.chdir(DATA)
    return prev


def resolve_data(p: str) -> str:
    """Путь из аргумента: как есть, если существует; иначе — относительно AIS\\data\\.

    Для скриптов, которым нельзя переходить в AIS\\data\\ целиком (панель Gradio:
    её --source может быть путём к видео относительно текущей папки)."""
    if not p or os.path.isabs(p) or os.path.exists(p):
        return p
    q = DATA / p
    return str(q) if q.exists() else p


def add_script_dir(file: str) -> None:
    """Сделать соседние скрипты импортируемыми (from analyse_new import ...),
    даже после to_data(): раньше это держалось на текущей папке."""
    d = str(Path(file).resolve().parent)
    if d not in sys.path:
        sys.path.insert(0, d)


def add_ros_pkg() -> None:
    """Сделать efe.py импортируемым вне ROS (панель, decision_rate.py)."""
    d = str(ROS_PKG)
    if d not in sys.path:
        sys.path.insert(0, d)


def add_wetlandbirds() -> None:
    """Сделать hmm_phases.py импортируемым: он лежит в AIS\\wetlandbirds\\.
    Раньше analyse_new.py искал его рядом с файлом разметки, где его не было,
    и часть с СММ молча пропускалась; boot.py работал только с PYTHONPATH."""
    d = str(WETLANDBIRDS)
    if d not in sys.path:
        sys.path.insert(0, d)
