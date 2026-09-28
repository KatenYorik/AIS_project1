# -*- coding: utf-8 -*-
"""Проверка окружения: что стоит, чего не хватает, всё ли нужных версий.

    python check_env.py

Запускать до установки и после. Ничего не меняет, только смотрит.
"""
from __future__ import annotations

import importlib, platform, shutil, subprocess, sys

# Консоль Windows по умолчанию не UTF-8, и питон падает на любом символе вне
# кодовой страницы. Одна строка снимает вопрос: пишем в UTF-8, а что не влезло —
# заменяем, но не роняем скрипт.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# (модуль, как называется в pip, зачем нужен, обязателен ли)
NEED = [
    ("numpy",       "numpy",            "всё считает",                        True),
    ("PIL",         "pillow",           "размеры кадров для CVAT",            True),
    ("cv2",         "opencv-python",    "чтение видео и кадров",              True),
    ("ultralytics", "ultralytics",      "обучение классификатора",            True),
    ("torch",       "(ставится с ultralytics)", "движок обучения",            True),
    ("onnx",        "onnx",             "формат экспорта",                    True),
    ("onnxruntime", "onnxruntime",      "быстрый прогон модели",              True),
    ("clearml",     "clearml",          "версии датасета и запуски",          True),
    ("gradio",      "gradio",           "панель для демо",                    True),
    ("rclpy",       "(только внутри ROS 2)", "узлы ROS 2",                    False),
]


def ver(mod):
    for attr in ("__version__", "version", "VERSION"):
        v = getattr(mod, attr, None)
        if isinstance(v, str): return v
    return "?"


def main():
    print("=" * 66)
    print("ОКРУЖЕНИЕ")
    print("=" * 66)
    print(f"питон:   {sys.version.split()[0]}  ({platform.system()} {platform.machine()})")
    print(f"где:     {sys.executable}")

    print("\n" + "=" * 66)
    print("ПАКЕТЫ")
    print("=" * 66)
    missing = []
    for mod, pipname, why, must in NEED:
        try:
            m = importlib.import_module(mod)
            print(f"  [+] {mod:14s} {ver(m):12s} - {why}")
        except Exception:
            mark = "[-]" if must else "[ ]"
            print(f"  {mark} {mod:14s} {'НЕТ':12s} - {why}"
                  + ("" if must else "   (нужен только для Проекта 2)"))
            if must: missing.append(pipname)

    print("\n" + "=" * 66)
    print("ВНЕШНИЕ ПРОГРАММЫ")
    print("=" * 66)
    for exe, why in (("ffmpeg", "нарезка кадров из видео"),
                     ("ffprobe", "длительность клипов"),
                     ("ros2", "узлы Проекта 2"),
                     ("colcon", "сборка пакета ROS 2")):
        p = shutil.which(exe)
        print(f"  {'[+]' if p else '[ ]'} {exe:8s} {'есть' if p else 'нет'}"
              + (f"  ({why})" if not p else ""))

    # ROS 2 отдельно: он может быть в WSL, а не здесь.
    # У команды ros2 НЕТ флага --version: версия узнаётся из переменной ROS_DISTRO.
    import os as _os
    distro = _os.environ.get("ROS_DISTRO")
    if distro:
        print(f"  дистрибутив ROS 2: {distro}")
    elif shutil.which("ros2"):
        print("  ros2 найден, но окружение не подключено — выполни:")
        print("    source /opt/ros/<дистрибутив>/setup.bash")
    else:
        print("  ROS 2 в этом окружении нет — это нормально, если он в WSL")

    # видеокарта, если есть
    try:
        import torch
        print("\n" + "=" * 66)
        print("ВЫЧИСЛЕНИЯ")
        print("=" * 66)
        if torch.cuda.is_available():
            print(f"  видеокарта: {torch.cuda.get_device_name(0)} — обучение будет быстрым")
        else:
            print("  видеокарты нет, обучение на процессоре")
            print(f"  ядер: {torch.get_num_threads()} — один запуск примерно 20-40 минут")
    except Exception:
        pass

    print("\n" + "=" * 66)
    if missing:
        print("ЧЕГО НЕ ХВАТАЕТ")
        print("=" * 66)
        print("  " + " ".join(sorted(set(missing))))
        print("\nпоставить всё разом:")
        print("  powershell -ExecutionPolicy Bypass -File setup_windows.ps1")
        print("или вручную:")
        print("  python -m pip install " + " ".join(sorted(set(missing))))
    else:
        print("ВСЁ НА МЕСТЕ для Проекта 1. Можно собирать датасет и обучать.")
    print("=" * 66)


if __name__ == "__main__":
    main()
